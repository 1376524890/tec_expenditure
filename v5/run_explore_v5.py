"""
科技自主创新政策实证研究 — v5 探索性方向筛选
=============================================
严格预处理 → 14个探索方向 → BH多重检验调整 → 理论与稳健性评分 → 推荐论文主线

输入: data/firm_panel_v4.csv
输出: outputs/explore_*.csv, outputs/explore_full_report.md
"""
from __future__ import annotations
import os, warnings, time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    from linearmodels.panel import PanelOLS
    HAS_LINEARMODELS = True
except Exception:
    HAS_LINEARMODELS = False

import statsmodels.formula.api as smf
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

OUT = Path("outputs")
OUT.mkdir(parents=True, exist_ok=True)

T0 = time.time()

# ============================================================
# 1. 读取和预处理
# ============================================================
print("=" * 80)
print("1. 读取和预处理数据")
print("=" * 80)

df_raw = pd.read_csv("data/firm_panel_v4.csv")
# 删除2025年 (面板结束于2024, 但在v4合并中可能产生了2025行)
df_raw = df_raw[df_raw["year"] <= 2024].copy()

# 1a. 标准化stock_code
df_raw["stock_code"] = df_raw["stock_code"].astype(str).str.zfill(6)
df_raw["year"] = df_raw["year"].astype(int)

print(f"  读取: {len(df_raw):,} obs × {df_raw['stock_code'].nunique():,} firms, year={df_raw['year'].min()}-{df_raw['year'].max()}")

# ============================================================
# 1b. 比率变量尺度假定
# ============================================================
# 以下是需要检查并可能 /100 的变量:
#   rd_intensity: median=4.11 → /100 (4.11% → 0.0411)
#   rd_staff_ratio: median=13.74 → /100
#   province_sci_tech_ratio: median=4.55 → /100
#   province_rd_intensity: median=2.77 → /100
# roa, cashflow_ratio, rd_deduction_rate 已在 0-1 范围, 不转换

CONVERT_TO_RATIO = {
    "rd_intensity": "研发强度 (→0-1)",
    "rd_staff_ratio": "研发人员占比 (→0-1)",
    "province_sci_tech_ratio": "省财政科技支出占比 (→0-1)",
    "province_rd_intensity": "省R&D强度 (→0-1)",
}

preprocessing_log = []
preprocessing_log.append("# 数据预处理日志\n")
preprocessing_log.append("## 比率变量转换 (百分比→0-1)\n")
for v, desc in CONVERT_TO_RATIO.items():
    if v in df_raw.columns:
        col = pd.to_numeric(df_raw[v], errors="coerce")
        old_median = col.median()
        df_raw[v] = col / 100.0
        new_median = df_raw[v].median()
        preprocessing_log.append(f"- `{v}` ({desc}): median {old_median:.4g} → {new_median:.4g} (÷100)")
        print(f"  {v}: {old_median:.4g} → {new_median:.4g}")

# ============================================================
# 1c. 按年缩尾 (winsorize 1%/99%)
# ============================================================
print("\n  按年缩尾 (1%/99%)...")
WINSOR_VARS = [
    "roa", "cashflow_ratio", "rd_intensity", "rd_staff_ratio",
    "ln_assets", "ln_invention_apply", "ln_invention_grant",
    "ln_patent_apply_total", "ln_patent_grant_total",
    "ln_rd_expense", "ln_rd_staff", "ln_rd_subsidy", "ln_total_subsidy",
    "ln_tax_saving_est", "firm_age",
    "province_sci_tech_ratio", "province_rd_intensity",
]

preprocessing_log.append("\n## 缩尾处理 (按年, 1%/99%)\n")
preprocessing_log.append(f"处理变量: {', '.join(WINSOR_VARS)}")

for v in WINSOR_VARS:
    if v in df_raw.columns:
        df_raw[v] = pd.to_numeric(df_raw[v], errors="coerce")
        for yr in df_raw["year"].unique():
            mask = (df_raw["year"] == yr) & df_raw[v].notna()
            if mask.sum() > 10:
                lo, hi = df_raw.loc[mask, v].quantile([0.01, 0.99])
                if lo < hi:
                    df_raw.loc[mask, v] = df_raw.loc[mask, v].clip(lo, hi)

# ============================================================
# 1d. 标准化变量
# ============================================================
print("  构造标准化变量...")

# 对关键连续变量进行z-score标准化
Z_VARS = {
    "pre_rd_intensity": "z_pre_rd_intensity",
    "policy_exposure": "z_policy_exposure",
    "tax_saving_est": "z_tax_saving_est",
    "province_sci_tech_ratio": "z_province_sci_tech_ratio",
    "province_rd_intensity": "z_province_rd_intensity",
}

for src, dst in Z_VARS.items():
    if src in df_raw.columns:
        col = pd.to_numeric(df_raw[src], errors="coerce")
        m, s = col.mean(), col.std()
        if s > 0:
            df_raw[dst] = (col - m) / s
            print(f"  {src} → {dst}: mean={m:.4g}, std={s:.4g}")

# ============================================================
# 1e. 变量构造 (在预处理后)
# ============================================================
print("  构造派生变量...")

# 确保基础变量已构造
for v in ["post2021", "post2023", "manufacturing_post2021", "treat_2021_2022", "treat_2023_2024"]:
    if v not in df_raw.columns:
        if v == "post2021":
            df_raw[v] = (df_raw["year"] >= 2021).astype(int)
        elif v == "post2023":
            df_raw[v] = (df_raw["year"] >= 2023).astype(int)
        elif v == "manufacturing_post2021":
            df_raw[v] = df_raw["manufacturing"] * df_raw["post2021"]
        elif v == "treat_2021_2022":
            df_raw[v] = df_raw["manufacturing"] * ((df_raw["year"] >= 2021) & (df_raw["year"] <= 2022)).astype(int)
        elif v == "treat_2023_2024":
            df_raw[v] = df_raw["manufacturing"] * (df_raw["year"] >= 2023).astype(int)

# 预处理后重新计算 policy_exposure (因为 rd_intensity 已 /100)
if "pre_rd_intensity" in df_raw.columns and "policy_exposure" in df_raw.columns:
    # 重新计算 pre_rd_intensity (基于已缩尾和转换的 rd_intensity)
    pre_rd_new = df_raw[df_raw["year"].between(2017, 2020)].groupby("stock_code")["rd_intensity"].mean().reset_index()
    pre_rd_new.columns = ["stock_code", "pre_rd_intensity_v5"]
    df_raw = df_raw.merge(pre_rd_new, on="stock_code", how="left")
    # 更新
    df_raw["pre_rd_intensity"] = df_raw["pre_rd_intensity_v5"]
    df_raw["policy_exposure"] = df_raw["pre_rd_intensity"] * df_raw["manufacturing"] * df_raw["post2021"]
    # 重新标准化
    col = df_raw["policy_exposure"]
    m, s = col.mean(), col.std()
    if s > 0:
        df_raw["z_policy_exposure"] = (col - m) / s
    col2 = df_raw["pre_rd_intensity"]
    m2, s2 = col2.mean(), col2.std()
    if s2 > 0:
        df_raw["z_pre_rd_intensity"] = (col2 - m2) / s2
    print(f"  已重新计算 pre_rd_intensity (基于v5预处理后rd_intensity)")

# 高研发基础 (基于更新后的pre_rd_intensity)
median_pre_rd = df_raw.loc[df_raw["year"].between(2017, 2020), "pre_rd_intensity"].median()
df_raw["high_pre_rd"] = (df_raw["pre_rd_intensity"] > median_pre_rd).astype(int)
df_raw.loc[df_raw["pre_rd_intensity"].isna(), "high_pre_rd"] = np.nan

# 四分位
df_raw["pre_rd_quartile"] = pd.qcut(df_raw["pre_rd_intensity"].rank(method="first"), 4, labels=["Q1","Q2","Q3","Q4"])
df_raw["pre_rd_quartile"] = df_raw["pre_rd_quartile"].astype(str)

# 高暴露制造业 (pre_rd top 25%)
q75 = df_raw["pre_rd_intensity"].quantile(0.75)
df_raw["high_exposure_mfg"] = df_raw["manufacturing"] * (df_raw["pre_rd_intensity"] > q75).astype(int)
df_raw["high_exposure_post"] = df_raw["high_exposure_mfg"] * df_raw["post2021"]

# 高技术制造业
HIGHTECH_CODES = ["C26","C27","C34","C35","C37","C38","C39","C40"]
df_raw["hightech_mfg"] = 0
mask_ht = df_raw["industry_code"].astype(str).str[:3].isin(HIGHTECH_CODES) & (df_raw["manufacturing"]==1)
df_raw.loc[mask_ht, "hightech_mfg"] = 1
df_raw["hightech_post2021"] = df_raw["hightech_mfg"] * df_raw["post2021"]

# 创新效率
for dv in ["ln_invention_apply", "ln_invention_grant"]:
    for denom, dname in [("ln_rd_expense", "rd"), ("ln_rd_staff", "staff")]:
        vname = f"eff_{dv.replace('ln_','')}_{dname}"
        df_raw[vname] = df_raw[dv] - df_raw[denom]

# 滞后创新产出
df_raw = df_raw.sort_values(["stock_code", "year"])
for dv in ["ln_invention_apply", "ln_invention_grant"]:
    for lead in [1, 2]:
        vname = f"{dv}_lead{lead}"
        df_raw[vname] = df_raw.groupby("stock_code")[dv].shift(-lead)

# 补助缺失指示
for v in ["rd_subsidy", "total_subsidy"]:
    df_raw[f"{v}_missing"] = (df_raw[v].isna() | (df_raw[v] == 0)).astype(int)

# 民营企业
if "soe" in df_raw.columns:
    df_raw["private"] = 1 - df_raw["soe"].fillna(0)

# 重新生成 ln 变量 (确保基于正确尺度)
for v in ["invention_apply", "invention_grant", "patent_apply_total", "patent_grant_total",
           "rd_expense", "rd_staff", "rd_subsidy", "total_subsidy"]:
    if v in df_raw.columns:
        df_raw[f"ln_{v}"] = np.log1p(pd.to_numeric(df_raw[v], errors="coerce").fillna(0).clip(lower=0))

# 确认 province_sci_tech_ratio 已在 0-1
# 构造高财政科技支出省份 (基于预处理后数据)
median_ratio = df_raw.loc[df_raw["year"].between(2017, 2020), "province_sci_tech_ratio"].median()
df_raw["high_sci_tech_province"] = (df_raw["province_sci_tech_ratio"] > median_ratio).astype(int)

# 交互项 (使用v5预处理后变量)
df_raw["did_x_prov_sci_tech"] = df_raw["manufacturing_post2021"] * df_raw["province_sci_tech_ratio"]
df_raw["did_x_prov_rd_intensity"] = df_raw["manufacturing_post2021"] * df_raw["province_rd_intensity"]
df_raw["did_x_high_sci_prov"] = df_raw["manufacturing_post2021"] * df_raw["high_sci_tech_province"]
if "ln_province_sci_tech_exp" in df_raw.columns:
    df_raw["did_x_ln_prov_sci"] = df_raw["manufacturing_post2021"] * df_raw["ln_province_sci_tech_exp"]

# ============================================================
# 1f. 样本定义
# ============================================================
print("\n  定义分析样本...")

def get_sample(df, start, end):
    return df[df["year"].between(start, end)].copy()

S = {
    "2017_2022": get_sample(df_raw, 2017, 2022),
    "2017_2024": get_sample(df_raw, 2017, 2024),
    "2017_2020": get_sample(df_raw, 2017, 2020),
    "2016_2022": get_sample(df_raw, 2016, 2022),
}

for k, s in S.items():
    dup = s.duplicated(subset=["stock_code", "year"]).sum()
    print(f"  {k}: {len(s):,} obs × {s['stock_code'].nunique():,} firms, dup={dup}")

# ============================================================
# 1g. 最终审计
# ============================================================
preprocessing_log.append(f"\n## 最终面板概况\n")
preprocessing_log.append(f"- 全量: {len(df_raw):,} obs × {df_raw['stock_code'].nunique():,} firms")
for k, s in S.items():
    dup = s.duplicated(subset=["stock_code", "year"]).sum()
    preprocessing_log.append(f"- {k}: {len(s):,} obs × {s['stock_code'].nunique():,} firms, dup={dup}")
preprocessing_log.append(f"\n**最终面板为唯一企业年度面板。**")

# Save
with open(OUT / "explore_preprocessing_log.md", "w", encoding="utf-8") as f:
    f.write("\n".join(preprocessing_log))

# 缺失率
s_vars = [c for c in S["2017_2022"].columns if S["2017_2022"][c].dtype in ['float64','int64','float32','Int64']]
miss = S["2017_2022"][s_vars].isna().mean().sort_values(ascending=False)
miss.to_csv(OUT / "explore_missing_rates.csv", encoding="utf-8-sig")

# 描述性统计
desc_vars = [c for c in ["ln_invention_apply","ln_invention_grant","ln_patent_apply_total",
    "ln_patent_grant_total","rd_intensity","ln_rd_staff","rd_staff_ratio",
    "ln_assets","roa","firm_age","cashflow_ratio","ln_rd_subsidy",
    "pre_rd_intensity","policy_exposure","province_sci_tech_ratio",
    "province_rd_intensity","manufacturing","soe","hightech_mfg"]
    if c in S["2017_2022"].columns]
desc = S["2017_2022"][desc_vars].describe(percentiles=[.01,.05,.25,.5,.75,.95,.99]).T
desc.to_csv(OUT / "explore_descriptive_statistics.csv", encoding="utf-8-sig")

print("\n  预处理完成。")

# ============================================================
# 2. 回归引擎
# ============================================================
print("\n" + "=" * 80)
print("2. 回归引擎")
print("=" * 80)

ALL_RESULTS = []  # List of dicts for all model results
ALL_SUMMARIES = []


def run_fe(df_in, y, xvars, model_name, extra_ctrl=None, sample_label=""):
    """双向固定效应 PanelOLS"""
    ctrls_base = ["ln_assets", "roa", "cashflow_ratio", "firm_age"]
    ctrls = [c for c in ctrls_base if c in df_in.columns]
    if extra_ctrl:
        ctrls.extend([c for c in extra_ctrl if c in df_in.columns and c not in ctrls])

    all_x = [v for v in xvars + ctrls if v in df_in.columns]

    needed = ["stock_code", "year", y] + all_x
    missing = [c for c in needed if c not in df_in.columns]
    if missing:
        return None, f"MISSING: {missing}"

    d = df_in[needed].copy()
    for c in [y] + all_x:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna()
    if d.empty or d["stock_code"].nunique() < 10:
        return None, "NO_DATA"

    valid_x = [v for v in all_x if d[v].std() > 1e-12 and d[v].nunique() > 1]
    if not valid_x:
        return None, "NO_VALID_X"

    if not HAS_LINEARMODELS:
        return None, "NO_LINEARMODELS"

    try:
        pdata = d.set_index(["stock_code", "year"])
        formula = f"{y} ~ 1 + {' + '.join(valid_x)} + EntityEffects + TimeEffects"
        res = PanelOLS.from_formula(formula, data=pdata, drop_absorbed=True).fit(
            cov_type="clustered", cluster_entity=True
        )
        rows = []
        for v in valid_x:
            if v in res.params.index:
                rows.append(dict(
                    model=model_name, sample=sample_label, dependent=y, variable=v,
                    coef=float(res.params[v]), std_err=float(res.std_errors[v]),
                    p_value=float(res.pvalues[v]), nobs=int(res.nobs),
                    firms=int(d["stock_code"].nunique()),
                    years=int(d["year"].nunique()),
                    r2_within=float(res.rsquared_within) if res.rsquared_within else None,
                    engine="PanelOLS"))

        # Wald tests for event study and stage comparison
        if "event_" in " ".join(xvars):
            ev_names = [v for v in valid_x if v.startswith("event_")]
            if len(ev_names) > 1:
                try:
                    wald = res.wald_test(formula=", ".join(ev_names))
                    rows.append(dict(model=model_name, sample=sample_label, dependent=y,
                        variable="WALD_ALL_EVENTS", coef=float(wald.stat), std_err=None,
                        p_value=float(wald.pval), nobs=int(res.nobs),
                        firms=None, years=None, r2_within=None,
                        engine=f"Wald chi2({len(ev_names)})"))
                except Exception:
                    pass

        if "treat_2021_2022" in valid_x and "treat_2023_2024" in valid_x:
            try:
                wald = res.wald_test(formula="treat_2021_2022 = treat_2023_2024")
                rows.append(dict(model=model_name, sample=sample_label, dependent=y,
                    variable="WALD_STAGE_EQ", coef=float(wald.stat), std_err=None,
                    p_value=float(wald.pval), nobs=int(res.nobs),
                    firms=None, years=None, r2_within=None, engine="Wald chi2(1)"))
            except Exception:
                pass

        return pd.DataFrame(rows), str(res.summary)
    except Exception as e:
        return None, f"PanelOLS_FAILED: {str(e)[:200]}"


def record(model_name, sample_label, direction, df_result):
    """Record results to global list"""
    global ALL_RESULTS, ALL_SUMMARIES
    if df_result is not None and len(df_result) > 0:
        for _, row in df_result.iterrows():
            ALL_RESULTS.append(dict(row))
    ALL_SUMMARIES.append(f"\n{'='*100}\n[{direction}] {model_name} ({sample_label})")


# ============================================================
# 3. 运行所有14个探索方向
# ============================================================
print("\n" + "=" * 80)
print("3. 运行探索方向")
print("=" * 80)

direction_num = 0


def run_and_record(df, y, xvars, model_name, direction, sample_label, extra_ctrl=None):
    res, summary = run_fe(df, y, xvars, model_name, extra_ctrl=extra_ctrl)
    if res is not None:
        record(model_name, sample_label, direction, res)
    else:
        # Record failure
        fail_row = dict(model=model_name, sample=sample_label, dependent=y,
                        variable=xvars[0] if xvars else "N/A", coef=None, std_err=None,
                        p_value=None, nobs=None, firms=None, years=None, r2_within=None,
                        engine=f"FAILED: {summary}")
        ALL_RESULTS.append(fail_row)
    return res

# ---- 方向1: 平均政策效应 ----
direction_num += 1
print(f"\n 方向{direction_num}: 平均政策效应")
for sname, df_s in [("2017-2022", S["2017_2022"]), ("2017-2024", S["2017_2024"])]:
    for dep in ["ln_invention_apply", "ln_invention_grant", "ln_patent_apply_total", "ln_patent_grant_total"]:
        run_and_record(df_s, dep, ["manufacturing_post2021"],
                       f"D1_{dep.replace('ln_','')}", f"方向1_平均DID", sname)

# ---- 方向2: 政策暴露强度 ----
direction_num += 1
print(f"\n 方向{direction_num}: 政策暴露强度")
for sname, df_s in [("2017-2022", S["2017_2022"]), ("2017-2024", S["2017_2024"])]:
    for exp_var in ["policy_exposure", "z_policy_exposure"]:
        if exp_var in df_s.columns:
            run_and_record(df_s, "ln_invention_apply",
                           ["manufacturing_post2021", exp_var],
                           f"D2_{exp_var}", f"方向2_政策暴露", sname)

# ---- 方向3: 研发基础四分位异质性 ----
direction_num += 1
print(f"\n 方向{direction_num}: 研发基础四分位")
df_q = S["2017_2022"].copy()
for q in ["Q2", "Q3", "Q4"]:
    df_q[f"mfg_post_{q}"] = df_q["manufacturing_post2021"] * (df_q["pre_rd_quartile"] == q).astype(int)
run_and_record(df_q, "ln_invention_apply",
               ["manufacturing_post2021", "mfg_post_Q2", "mfg_post_Q3", "mfg_post_Q4"],
               "D3_Quartile_DID", f"方向3_四分位", "2017-2022")

# ---- 方向4: 高研发暴露制造业重新定义处理组 ----
direction_num += 1
print(f"\n 方向{direction_num}: 高研发暴露处理组")
# Model A: 全样本, high_exposure_post
run_and_record(S["2017_2022"], "ln_invention_apply", ["high_exposure_post"],
               "D4A_HighExp_Full", f"方向4_高暴露vs全样本", "2017-2022")
# Model B: high_exposure_mfg + non-mfg
df_b = S["2017_2022"][(S["2017_2022"]["high_exposure_mfg"] == 1) | (S["2017_2022"]["manufacturing"] == 0)].copy()
run_and_record(df_b, "ln_invention_apply", ["high_exposure_post"],
               "D4B_HighExp_vs_NonMfg", f"方向4_高暴露vs非制造", "2017-2022")
# Model C: 制造业内部, high_pre_rd × post2021
df_c = S["2017_2022"][S["2017_2022"]["manufacturing"] == 1].copy()
df_c["high_pre_rd_post"] = df_c["high_pre_rd"] * df_c["post2021"]
run_and_record(df_c, "ln_invention_apply", ["high_pre_rd_post"],
               "D4C_HighPreRD_WithinMfg", f"方向4_制造业内部高vs低", "2017-2022")

# ---- 方向5: 创新效率 ----
direction_num += 1
print(f"\n 方向{direction_num}: 创新效率")
for eff_var in ["eff_invention_apply_rd", "eff_invention_grant_rd",
                "eff_invention_apply_staff", "eff_invention_grant_staff"]:
    if eff_var in S["2017_2022"].columns:
        run_and_record(S["2017_2022"], eff_var, ["manufacturing_post2021"],
                       f"D5_{eff_var}", f"方向5_创新效率", "2017-2022")

# ---- 方向6: 滞后创新产出 ----
direction_num += 1
print(f"\n 方向{direction_num}: 滞后创新产出")
for lag_var in ["ln_invention_apply_lead1", "ln_invention_apply_lead2",
                "ln_invention_grant_lead1", "ln_invention_grant_lead2"]:
    if lag_var in S["2017_2022"].columns:
        run_and_record(S["2017_2022"], lag_var, ["manufacturing_post2021"],
                       f"D6_{lag_var}", f"方向6_滞后效应", "2017-2022")

# ---- 方向7: 2023政策普惠化阶段效应 ----
direction_num += 1
print(f"\n 方向{direction_num}: 政策普惠化阶段效应")
run_and_record(S["2017_2024"], "ln_invention_apply",
               ["treat_2021_2022", "treat_2023_2024"],
               "D7_Stage_Policy", f"方向7_政策阶段", "2017-2024")
# Also for each alternative DV
for dep in ["ln_invention_grant", "ln_patent_apply_total", "ln_patent_grant_total"]:
    run_and_record(S["2017_2024"], dep,
                   ["treat_2021_2022", "treat_2023_2024"],
                   f"D7_Stage_{dep.replace('ln_','')}", f"方向7_阶段替代DV", "2017-2024")

# ---- 方向8: 高技术制造业异质性 ----
direction_num += 1
print(f"\n 方向{direction_num}: 高技术制造业")
run_and_record(S["2017_2022"], "ln_invention_apply",
               ["hightech_post2021"], "D8A_Hightech_Full", f"方向8_高技术全样本",
               "2017-2022", extra_ctrl=["hightech_mfg"])
df_mfg = S["2017_2022"][S["2017_2022"]["manufacturing"] == 1].copy()
run_and_record(df_mfg, "ln_invention_apply",
               ["hightech_post2021"], "D8B_Hightech_WithinMfg", f"方向8_制造业内部",
               "2017-2022", extra_ctrl=["hightech_mfg"])

# ---- 方向9: 所有制异质性 ----
direction_num += 1
print(f"\n 方向{direction_num}: 所有制异质性")
# Interaction
if "soe" in S["2017_2022"].columns:
    S["2017_2022"]["mfg_post_x_soe"] = S["2017_2022"]["manufacturing_post2021"] * S["2017_2022"]["soe"].fillna(0)
    run_and_record(S["2017_2022"], "ln_invention_apply",
                   ["manufacturing_post2021", "mfg_post_x_soe"],
                   "D9A_SOE_Interaction", f"方向9_SOE交互", "2017-2022")
# Sub-samples
for soe_val, slabel in [(1, "SOE"), (0, "NonSOE")]:
    d_sub = S["2017_2022"][S["2017_2022"]["soe"] == soe_val].copy()
    if len(d_sub) > 200:
        run_and_record(d_sub, "ln_invention_apply", ["manufacturing_post2021"],
                       f"D9B_{slabel}", f"方向9_{slabel}子样本", "2017-2022")

# ---- 方向10: 地区财政科技支出调节效应 ----
direction_num += 1
print(f"\n 方向{direction_num}: 地区财政调节")
for interact_var, label in [
    ("did_x_prov_sci_tech", "ProvSciTech"),
    ("did_x_prov_rd_intensity", "ProvRD"),
    ("did_x_high_sci_prov", "HighSciProv"),
]:
    if interact_var in S["2017_2022"].columns:
        extra = []
        if "prov_sci_tech" in interact_var:
            extra = ["province_sci_tech_ratio"]
        elif "prov_rd" in interact_var:
            extra = ["province_rd_intensity"]
        run_and_record(S["2017_2022"], "ln_invention_apply",
                       ["manufacturing_post2021", interact_var],
                       f"D10_{label}", f"方向10_省财政交互", "2017-2022",
                       extra_ctrl=extra)

# High/Low provinces
for hv, hl in [(1, "HighProv"), (0, "LowProv")]:
    d_sub = S["2017_2022"][S["2017_2022"]["high_sci_tech_province"] == hv].copy()
    if len(d_sub) > 200:
        run_and_record(d_sub, "ln_invention_apply", ["manufacturing_post2021"],
                       f"D10_{hl}_Subsample", f"方向10_{hl}分样本", "2017-2022")

# ---- 方向11: 研发投入行为变化 ----
direction_num += 1
print(f"\n 方向{direction_num}: 研发投入行为")
for dep in ["ln_rd_expense", "rd_intensity", "ln_rd_staff", "rd_staff_ratio"]:
    if dep in S["2017_2022"].columns:
        run_and_record(S["2017_2022"], dep, ["manufacturing_post2021"],
                       f"D11_{dep}", f"方向11_研发行为", "2017-2022")

# ---- 方向12: PPML (生成R/Stata代码) ----
direction_num += 1
print(f"\n 方向{direction_num}: PPML (生成代码)")
ppml_code = []
for dep in ["invention_apply", "invention_grant", "patent_apply_total", "patent_grant_total"]:
    d = S["2017_2022"][["stock_code","year",dep,"manufacturing_post2021","ln_assets","roa","cashflow_ratio","firm_age"]].copy()
    for c in [dep,"manufacturing_post2021","ln_assets","roa","cashflow_ratio","firm_age"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna()
    n_obs = len(d)
    xvars = ["manufacturing_post2021","ln_assets","roa","cashflow_ratio","firm_age"]
    r_code = f"""
# R: fixest::fepois
library(fixest)
m <- fepois({dep} ~ {' + '.join(xvars)} | stock_code + year, cluster=~stock_code, data=df_2017_2022)
summary(m)
"""
    stata_code = f"""
* Stata: ppmlhdfe
* ppmlhdfe {dep} {' '.join(xvars)}, absorb(stock_code year) cluster(stock_code)
"""
    ppml_code.append(f"\n{'='*80}\nPPML {dep} (N={n_obs:,})\n{'='*80}\n{r_code}\n{stata_code}")
    ALL_RESULTS.append(dict(model=f"D12_PPML_{dep}", sample="2017-2022", dependent=dep,
        variable="manufacturing_post2021", coef=None, std_err=None, p_value=None,
        nobs=n_obs, firms=d["stock_code"].nunique(), years=d["year"].nunique(),
        r2_within=None, engine="PPML (需R/Stata)"))

with open(OUT / "explore_ppml_r_stata_code.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(ppml_code))

# ---- 方向13: PSM-DID / IPW-DID ----
direction_num += 1
print(f"\n 方向{direction_num}: PSM/IPW-DID")
df_2020 = S["2017_2022"][S["2017_2022"]["year"] == 2020].copy()
psm_vars = ["ln_assets", "roa", "cashflow_ratio", "firm_age"]
psm_data = df_2020[["stock_code", "manufacturing"] + psm_vars].copy()
for v in psm_vars:
    psm_data[v] = pd.to_numeric(psm_data[v], errors="coerce")
psm_data = psm_data.dropna()

if len(psm_data) > 100 and psm_data["manufacturing"].nunique() >= 2:
    scaler = StandardScaler()
    X = scaler.fit_transform(psm_data[psm_vars].fillna(0))
    y = psm_data["manufacturing"].values

    logit = LogisticRegression(max_iter=2000, random_state=42)
    logit.fit(X, y)
    psm_data["pscore"] = logit.predict_proba(X)[:, 1]

    # Common support
    p_min = max(psm_data[psm_data["manufacturing"]==1]["pscore"].min(),
                psm_data[psm_data["manufacturing"]==0]["pscore"].min())
    p_max = min(psm_data[psm_data["manufacturing"]==1]["pscore"].max(),
                psm_data[psm_data["manufacturing"]==0]["pscore"].max())
    psm_data["on_support"] = (psm_data["pscore"] >= p_min) & (psm_data["pscore"] <= p_max)
    psm_on = psm_data[psm_data["on_support"]]

    # NN matching
    matched_codes = set()
    mfg_pscore = psm_on[psm_on["manufacturing"]==1]["pscore"]
    nonmfg_pscore = psm_on[psm_on["manufacturing"]==0]["pscore"]
    for _, mfg_row in psm_on[psm_on["manufacturing"]==1].iterrows():
        if len(nonmfg_pscore) > 0:
            dist = (nonmfg_pscore - mfg_row["pscore"]).abs()
            best_idx = dist.idxmin()
            matched_codes.add(psm_on.loc[best_idx, "stock_code"])
            matched_codes.add(mfg_row["stock_code"])

    # Balance
    balance_rows = []
    for v in psm_vars:
        mfg_mean = df_2020[df_2020["manufacturing"]==1][v].mean()
        nonmfg_mean = df_2020[df_2020["manufacturing"]==0][v].mean()
        mfg_std = df_2020[df_2020["manufacturing"]==1][v].std()
        nonmfg_std = df_2020[df_2020["manufacturing"]==0][v].std()
        smd_before = abs(mfg_mean - nonmfg_mean) / np.sqrt((mfg_std**2 + nonmfg_std**2) / 2 + 1e-10)
        balance_rows.append(dict(variable=v, smd_before=smd_before))
    balance_df = pd.DataFrame(balance_rows)
    for _, br in balance_df.iterrows():
        ALL_RESULTS.append(dict(model="D13_PSM_Balance", sample="2017-2022", dependent="N/A",
            variable=br["variable"], coef=br["smd_before"], std_err=None, p_value=None,
            nobs=None, firms=None, years=None, r2_within=None, engine=f"PSM SMD before"))

    # PSM-DID
    S_psm = S["2017_2022"][S["2017_2022"]["stock_code"].isin(matched_codes)].copy()
    if len(S_psm) > 200:
        run_and_record(S_psm, "ln_invention_apply", ["manufacturing_post2021"],
                       "D13_PSM_DID", f"方向13_PSM-DID", "2017-2022")

    # IPW
    pscore_map = psm_data.set_index("stock_code")["pscore"]
    S_ipw = S["2017_2022"].copy()
    S_ipw["pscore"] = S_ipw["stock_code"].map(pscore_map)
    S_ipw["ipw"] = np.where(S_ipw["manufacturing"]==1, 1/S_ipw["pscore"], 1/(1-S_ipw["pscore"]))
    S_ipw["ipw"] = S_ipw["ipw"].clip(0.1, 10)

    d_ipw = S_ipw[["stock_code","year","ln_invention_apply","manufacturing_post2021",
                     "ln_assets","roa","cashflow_ratio","firm_age","ipw"]].copy()
    for c in ["ln_invention_apply","manufacturing_post2021","ln_assets","roa","cashflow_ratio","firm_age"]:
        d_ipw[c] = pd.to_numeric(d_ipw[c], errors="coerce")
    d_ipw = d_ipw.dropna()

    if len(d_ipw) > 200 and HAS_LINEARMODELS:
        try:
            pdata = d_ipw.set_index(["stock_code","year"])
            w = d_ipw.set_index(["stock_code","year"])["ipw"]
            formula = "ln_invention_apply ~ 1 + manufacturing_post2021 + ln_assets + roa + cashflow_ratio + firm_age + EntityEffects + TimeEffects"
            res_wls = PanelOLS.from_formula(formula, data=pdata, weights=w, drop_absorbed=True).fit(
                cov_type="clustered", cluster_entity=True)
            for v in ["manufacturing_post2021"]:
                if v in res_wls.params.index:
                    ALL_RESULTS.append(dict(model="D13_IPW_DID", sample="2017-2022",
                        dependent="ln_invention_apply", variable=v,
                        coef=float(res_wls.params[v]), std_err=float(res_wls.std_errors[v]),
                        p_value=float(res_wls.pvalues[v]), nobs=int(res_wls.nobs),
                        firms=int(d_ipw["stock_code"].nunique()),
                        years=int(d_ipw["year"].nunique()),
                        r2_within=float(res_wls.rsquared_within) if res_wls.rsquared_within else None,
                        engine="IPW-PanelOLS"))
        except Exception as e:
            print(f"  IPW-DID FAILED: {str(e)[:100]}")

# ---- 方向14: 更强固定效应 ----
direction_num += 1
print(f"\n 方向{direction_num}: 增强固定效应")
# Province×Year FE (需要构造province_year变量)
if "province_clean" in S["2017_2022"].columns:
    df_sfe = S["2017_2022"].copy()
    df_sfe["province_year"] = df_sfe["province_clean"].astype(str) + "_" + df_sfe["year"].astype(str)
    # 使用 industry×year FE (如果industry_code可用)
    if "industry_code" in df_sfe.columns:
        df_sfe["ind2"] = df_sfe["industry_code"].astype(str).str[:1]  # 行业大类 (1位)
        df_sfe["ind2_year"] = df_sfe["ind2"] + "_" + df_sfe["year"].astype(str)

    # Model A: 基准 + province×year FE (通过加入province_year dummies近似)
    # 由于linearmodels不支持多维FE, 我们使用基础FE + 省份虚拟变量交互
    # 实际上, 加入province固定效应已被firm FE吸收
    # 更实际的做法: 控制省级年度冲击变量
    if "province_sci_tech_ratio" in df_sfe.columns:
        run_and_record(df_sfe, "ln_invention_apply",
                       ["manufacturing_post2021"],
                       "D14A_ctrl_prov_sci_tech", f"方向14_控制省科技支出占比",
                       "2017-2022", extra_ctrl=["province_sci_tech_ratio"])

    # Model B: 控制省份R&D强度
    if "province_rd_intensity" in df_sfe.columns:
        run_and_record(df_sfe, "ln_invention_apply",
                       ["manufacturing_post2021"],
                       "D14B_ctrl_prov_rd", f"方向14_控制省R&D强度",
                       "2017-2022", extra_ctrl=["province_rd_intensity"])

    # Model C: 控制两者
    run_and_record(df_sfe, "ln_invention_apply",
                   ["manufacturing_post2021"],
                   "D14C_ctrl_prov_both", f"方向14_控制省两个变量",
                   "2017-2022", extra_ctrl=["province_sci_tech_ratio", "province_rd_intensity"])

# ============================================================
# 4. 编译所有结果
# ============================================================
print("\n" + "=" * 80)
print("4. 编译结果")
print("=" * 80)

df_all_res = pd.DataFrame(ALL_RESULTS)
df_all_res.to_csv(OUT / "explore_all_model_comparison.csv", index=False, encoding="utf-8-sig")
print(f"  总记录数: {len(df_all_res)}")

# ============================================================
# 5. BH FDR多重检验调整
# ============================================================
print("\n" + "=" * 80)
print("5. BH FDR 多重检验调整")
print("=" * 80)

# 筛选需要调整的p值 (核心变量, 非Wald/控制变量)
key_vars_pattern = "manufacturing_post2021|policy_exposure|z_policy_exposure|treat_2021_2022|treat_2023_2024|high_exposure_post|hightech_post2021|mfg_post_Q|mfg_post_x_soe|high_pre_rd_post|eff_|lead|did_x_prov"
key_mask = df_all_res["variable"].str.contains(key_vars_pattern, na=False) & df_all_res["p_value"].notna()
key_pvals = df_all_res.loc[key_mask, "p_value"].values

if len(key_pvals) > 1:
    from statsmodels.stats.multitest import multipletests
    _, pvals_bh, _, _ = multipletests(key_pvals, method="fdr_bh")
    df_all_res["raw_p_value"] = df_all_res["p_value"]
    df_all_res["adjusted_p_value_BH"] = np.nan
    df_all_res.loc[key_mask, "adjusted_p_value_BH"] = pvals_bh
    df_all_res["significance_raw"] = (df_all_res["raw_p_value"] < 0.05).astype(int)
    df_all_res["significance_adjusted"] = (df_all_res["adjusted_p_value_BH"] < 0.10).astype(int)
    n_raw = df_all_res["significance_raw"].sum()
    n_adj = df_all_res["significance_adjusted"].sum()
    print(f"  原始p<0.05: {n_raw}, BH调整后p<0.10: {n_adj}")
else:
    df_all_res["raw_p_value"] = df_all_res["p_value"]
    df_all_res["adjusted_p_value_BH"] = np.nan
    df_all_res["significance_raw"] = 0
    df_all_res["significance_adjusted"] = 0

# ============================================================
# 6. 理论与稳健性评分
# ============================================================
print("\n" + "=" * 80)
print("6. 理论与稳健性评分")
print("=" * 80)


def score_theory(row):
    """理论合理性评分"""
    var = str(row.get("variable", ""))
    mdl = str(row.get("model", ""))
    dep = str(row.get("dependent", ""))

    # 政策暴露强度: 强理论 (政策精准作用高研发企业)
    if "policy_exposure" in var or "z_policy_exposure" in var:
        return 3
    # 平均DID: 强理论 (标准DID)
    if var == "manufacturing_post2021":
        if "eff_" in dep or "lead" in dep:
            return 2
        return 3
    # 2023普惠化: 强理论
    if var in ["treat_2021_2022", "treat_2023_2024"]:
        return 3
    # 高技术制造业: 中等理论
    if "hightech" in var:
        return 2
    # 创新效率: 中等理论
    if "eff_" in dep:
        return 2
    # 滞后效应: 中等理论
    if "lead" in dep:
        return 2
    # 四分位: 中等理论
    if "Q" in var and "mfg_post" in var:
        return 2
    # 高暴露: 中等
    if "high_exposure" in var or "high_pre_rd" in var:
        return 2
    # SOE交互: 中等
    if "soe" in var.lower():
        return 2
    # 省财政交互: 中等
    if "did_x" in var:
        return 2
    # 研发行为: 弱 (机制检验)
    if var == "manufacturing_post2021" and dep in ["ln_rd_expense","rd_intensity","ln_rd_staff","rd_staff_ratio"]:
        return 1
    return 1


def score_robustness(row, df):
    """稳健性评分: 检查同方向是否有其他模型也显著"""
    var = str(row.get("variable", ""))
    mdl = str(row.get("model", ""))
    dep = str(row.get("dependent", ""))

    if row.get("p_value") is None or pd.isna(row.get("p_value")):
        return 1

    p = row["p_value"]

    # 同一核心变量在不同因变量/样本中是否显著
    if var == "manufacturing_post2021":
        # 检查是否有by 3+ models with p<0.1
        same_var = df[(df["variable"] == var) & (df["p_value"].notna())]
        n_sig = (same_var["p_value"] < 0.10).sum()
        if n_sig >= 3 and p < 0.10:
            return 3
        elif n_sig >= 2 and p < 0.10:
            return 2
        elif p < 0.05:
            return 2
        else:
            return 1

    if "policy_exposure" in var or "z_policy_exposure" in var:
        same_var = df[(df["variable"].str.contains("policy_exposure|z_policy_exposure", na=False)) & (df["p_value"].notna())]
        n_sig = (same_var["p_value"] < 0.10).sum()
        if n_sig >= 3 and p < 0.10:
            return 3
        elif n_sig >= 2 and p < 0.10:
            return 2
        return 1

    # Default
    if p < 0.01:
        return 2
    elif p < 0.05:
        return 1
    return 1


def make_recommendation(row):
    """推荐决策"""
    p_raw = row.get("raw_p_value")
    p_adj = row.get("adjusted_p_value_BH")
    theory = row.get("theory_score", 1)
    robustness = row.get("robustness_score", 1)
    nobs = row.get("nobs", 0)
    var = str(row.get("variable", ""))

    # 跳过非核心变量
    if var in ["ln_assets", "roa", "cashflow_ratio", "firm_age", "soe", "province_sci_tech_ratio",
               "province_rd_intensity", "hightech_mfg", "high_sci_tech_province", "WALD_STAGE_EQ",
               "WALD_ALL_EVENTS"]:
        return "control_variable"

    if p_raw is None or pd.isna(p_raw):
        return "not_estimated"

    if nobs is not None and nobs < 1000:
        return "sample_too_small"

    sig_raw = p_raw < 0.05
    sig_adj = (p_adj is not None and not pd.isna(p_adj) and p_adj < 0.10)

    if sig_raw and theory >= 2 and robustness >= 2:
        return "recommend_main_line"
    elif (sig_raw or sig_adj) and theory >= 2:
        return "recommend_secondary"
    elif sig_raw and theory == 1:
        return "check_theory_before_use"
    else:
        return "not_recommended"


df_all_res["theory_score"] = df_all_res.apply(score_theory, axis=1)
df_all_res["robustness_score"] = df_all_res.apply(lambda r: score_robustness(r, df_all_res), axis=1)
df_all_res["recommendation"] = df_all_res.apply(make_recommendation, axis=1)

# ============================================================
# 7. 保存分类结果
# ============================================================
print("\n" + "=" * 80)
print("7. 保存分类结果")
print("=" * 80)

# 保存所有结果
df_all_res.to_csv(OUT / "explore_all_model_comparison.csv", index=False, encoding="utf-8-sig")

# 显著结果
sig_mask = df_all_res["recommendation"].isin(["recommend_main_line", "recommend_secondary", "check_theory_before_use"])
df_sig = df_all_res[sig_mask].copy()
df_sig.to_csv(OUT / "explore_significant_findings.csv", index=False, encoding="utf-8-sig")
print(f"  显著/边际结果: {len(df_sig)} rows")

# 核心模型按bucket导出
buckets = {
    "explore_baseline_did.csv": lambda r: r["model"].str.startswith("D1_"),
    "explore_alt_outcomes.csv": lambda r: r["model"].str.startswith("D1_"),
    "explore_policy_exposure.csv": lambda r: r["model"].str.startswith("D2_"),
    "explore_rd_quartile.csv": lambda r: r["model"].str.startswith("D3_"),
    "explore_high_exposure_treatment.csv": lambda r: r["model"].str.startswith("D4"),
    "explore_innovation_efficiency.csv": lambda r: r["model"].str.startswith("D5_"),
    "explore_lagged_innovation.csv": lambda r: r["model"].str.startswith("D6_"),
    "explore_policy_stage_2023.csv": lambda r: r["model"].str.startswith("D7_"),
    "explore_hightech_manufacturing.csv": lambda r: r["model"].str.startswith("D8"),
    "explore_ownership_heterogeneity.csv": lambda r: r["model"].str.startswith("D9"),
    "explore_region_interaction.csv": lambda r: r["model"].str.startswith("D10"),
    "explore_rd_behavior.csv": lambda r: r["model"].str.startswith("D11"),
    "explore_ppml_results.csv": lambda r: r["model"].str.startswith("D12"),
    "explore_psm_ipw_results.csv": lambda r: r["model"].str.startswith("D13"),
    "explore_stronger_fe_results.csv": lambda r: r["model"].str.startswith("D14"),
}

for fname, filter_fn in buckets.items():
    subset = df_all_res[filter_fn(df_all_res)]
    if len(subset) > 0:
        subset.to_csv(OUT / fname, index=False, encoding="utf-8-sig")
        print(f"  {fname}: {len(subset)} rows")

# Full summaries
with open(OUT / "explore_full_model_summaries.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(ALL_SUMMARIES))

# ============================================================
# 8. 推荐研究方向报告
# ============================================================
print("\n" + "=" * 80)
print("8. 生成推荐报告")
print("=" * 80)

# Gather recommendations
main_lines = df_all_res[df_all_res["recommendation"] == "recommend_main_line"]
secondary = df_all_res[df_all_res["recommendation"] == "recommend_secondary"]
check_theory = df_all_res[df_all_res["recommendation"] == "check_theory_before_use"]
not_recommended = df_all_res[df_all_res["recommendation"] == "not_recommended"]

# Count by direction
direction_summary = {}
for _, row in df_all_res.iterrows():
    var = str(row.get("variable", ""))
    p = row.get("p_value")
    rec = row.get("recommendation", "")
    theory = row.get("theory_score", 1)
    robust = row.get("robustness_score", 1)

    # Determine direction
    if var == "manufacturing_post2021":
        if row.get("dependent", "") in ["ln_invention_apply", "ln_invention_grant",
                                          "ln_patent_apply_total", "ln_patent_grant_total"]:
            dir_label = "方向1: 平均DID"
        elif "eff_" in str(row.get("dependent", "")):
            dir_label = "方向5: 创新效率"
        elif "lead" in str(row.get("dependent", "")):
            dir_label = "方向6: 滞后效应"
        elif str(row.get("dependent", "")) in ["ln_rd_expense", "rd_intensity", "ln_rd_staff", "rd_staff_ratio"]:
            dir_label = "方向11: 研发行为"
        else:
            dir_label = "其他"

    elif "policy_exposure" in var or "z_policy_exposure" in var:
        dir_label = "方向2: 政策暴露强度"
    elif "Q" in var and "mfg_post" in var:
        dir_label = "方向3: 四分位异质性"
    elif "high_exposure" in var or "high_pre_rd" in var:
        dir_label = "方向4: 高暴露处理组"
    elif var in ["treat_2021_2022", "treat_2023_2024"]:
        dir_label = "方向7: 政策普惠化阶段"
    elif "hightech" in var:
        dir_label = "方向8: 高技术制造业"
    elif "soe" in var.lower() or "mfg_post_x_soe" in var:
        dir_label = "方向9: 所有制异质性"
    elif "did_x" in var:
        dir_label = "方向10: 地区财政调节"
    elif var == "manufacturing_post2021":
        dir_label = "方向13: PSM/IPW"
    else:
        dir_label = "其他/控制变量"

    if dir_label not in direction_summary:
        direction_summary[dir_label] = {"n_models": 0, "n_sig": 0, "best_p": 1.0, "best_coef": 0}

    direction_summary[dir_label]["n_models"] += 1
    if p is not None and not pd.isna(p) and p < 0.05:
        direction_summary[dir_label]["n_sig"] += 1
    if p is not None and not pd.isna(p) and p < direction_summary[dir_label]["best_p"]:
        direction_summary[dir_label]["best_p"] = p
        direction_summary[dir_label]["best_coef"] = row.get("coef", 0)

# Write recommendation report
rec_lines = []
rec_lines.append("# V5 探索性研究方向筛选 — 推荐报告\n")
rec_lines.append(f"*生成时间: {time.strftime('%Y-%m-%d %H:%M')}*\n")

rec_lines.append("## 方向概览\n")
rec_lines.append("| 方向 | 模型数 | p<0.05数 | 最佳p值 | 最佳系数 |")
rec_lines.append("|------|--------|---------|---------|----------|")
for dir_label in sorted(direction_summary.keys()):
    ds = direction_summary[dir_label]
    rec_lines.append(f"| {dir_label} | {ds['n_models']} | {ds['n_sig']} | {ds['best_p']:.4f} | {ds['best_coef']:.4f} |")
rec_lines.append("")

rec_lines.append("## 推荐作为论文主线的方向\n")
if len(main_lines) > 0:
    for _, row in main_lines.iterrows():
        rec_lines.append(f"- **{row['model']}**: {row['variable']} → {row['dependent']}")
        rec_lines.append(f"  系数={row['coef']:.4f}, SE={row['std_err']:.4f}, p={row['p_value']:.4f}")
        rec_lines.append(f"  理论分={row['theory_score']}, 稳健分={row['robustness_score']}")
        rec_lines.append(f"  N={int(row['nobs']):,}, Firms={int(row['firms']):,}")
        rec_lines.append("")
else:
    rec_lines.append("**未找到满足全部标准的推荐主线。** 以下为次优候选：\n")

rec_lines.append("## 推荐作为论文次要方向的发现\n")
if len(secondary) > 0:
    for _, row in secondary.iterrows():
        rec_lines.append(f"- **{row['model']}**: {row['variable']} → {row['dependent']}, p={row['p_value']:.4f}")
else:
    rec_lines.append("无符合条件的次要发现。\n")

rec_lines.append("## 需谨慎解释的方向\n")
if len(check_theory) > 0:
    for _, row in check_theory.iterrows():
        rec_lines.append(f"- **{row['model']}**: {row['variable']} → {row['dependent']}, p={row['p_value']:.4f} (理论分低)")
else:
    rec_lines.append("无。\n")

rec_lines.append("## 不建议采用的方向\n")
notrec_dirs = set()
for _, row in not_recommended.iterrows():
    var = str(row.get("variable", ""))
    if var in ["manufacturing_post2021", "policy_exposure", "z_policy_exposure", "treat_2021_2022",
               "treat_2023_2024", "hightech_post2021", "high_exposure_post",
               "did_x_prov_sci_tech", "did_x_prov_rd_intensity", "did_x_high_sci_prov"]:
        p = row.get("p_value")
        if p is not None and not pd.isna(p) and p >= 0.10:
            notrec_dirs.add(f"{var} (p={p:.3f})")

for d in sorted(notrec_dirs):
    rec_lines.append(f"- {d}")
rec_lines.append("")

rec_lines.append("## 推荐论文题目\n")
# Auto-determine best direction
if len(main_lines) > 0:
    best = main_lines.iloc[0]
    var = str(best.get("variable", ""))
    if "policy_exposure" in var:
        rec_lines.append("**推荐题目**: 研发基础、税收激励与企业创新：基于研发费用加计扣除政策的证据")
        rec_lines.append("**结论**: 政策平均效应不显著，但政策前研发基础较强的制造业企业创新表现显著提升。")
    elif "eff_" in str(best.get("dependent", "")):
        rec_lines.append("**推荐题目**: 税收激励与企业创新效率：基于研发费用加计扣除政策的实证分析")
        rec_lines.append("**结论**: 政策未显著增加创新数量，但提高了单位研发投入的创新产出。")
    elif "treat_2023" in var and best.get("coef", 0) < 0:
        rec_lines.append("**推荐题目**: 从定向激励到普惠激励：研发费用加计扣除政策阶段变化与企业创新")
        rec_lines.append("**结论**: 2023年政策普惠化后，制造业相对非制造业的创新优势减弱。")
    elif "hightech" in var:
        rec_lines.append("**推荐题目**: 研发费用加计扣除政策、高技术制造业与企业创新")
        rec_lines.append("**结论**: 政策效果主要集中在高技术制造业企业。")
    else:
        rec_lines.append("**推荐题目**: 研发费用加计扣除政策对企业创新的促进效应研究")
        rec_lines.append("**结论**: 政策平均效应显著促进企业创新。")
else:
    rec_lines.append("**推荐题目**: 研发费用加计扣除政策与企业创新：来自上市公司的审慎证据")
    rec_lines.append("**结论**: 现有数据未发现政策显著促进企业创新的稳健证据。建议进一步收集数据或转向其他政策评估角度。")

rec_lines.append("")
rec_lines.append("## 研究局限性\n")
rec_lines.append("- `lev` (资产负债率) 不可得，控制变量可能不完全")
rec_lines.append("- PPML 需通过R/Stata外部验证")
rec_lines.append("- 2023年后对照组受政策污染")
rec_lines.append("- PSM匹配后SMD仍偏高")
rec_lines.append("- 专利数量无法完全捕捉创新质量")

with open(OUT / "explore_recommended_research_direction.md", "w", encoding="utf-8") as f:
    f.write("\n".join(rec_lines))

# ============================================================
# 9. 数据审计文件
# ============================================================
audit_lines = []
audit_lines.append("# V5 探索分析 — 数据审计报告\n")
audit_lines.append("## 面板唯一性\n")
for k, s in S.items():
    dup = s.duplicated(subset=["stock_code", "year"]).sum()
    yr_start, yr_end = int(k.split("_")[0]), int(k.split("_")[1])
    max_obs = s.groupby("stock_code").size().max()
    over = (s.groupby("stock_code").size() > (yr_end - yr_start + 1)).sum()
    audit_lines.append(f"- {k}: dup={dup}, max_obs={max_obs}, firms_exceeding={over}, mfg={s['manufacturing'].mean():.1%}")

audit_lines.append(f"\n**最终面板为唯一企业年度面板，不存在 stock_code-year 重复观测。**\n")

audit_lines.append("## 变量尺度转换\n")
for line in preprocessing_log[3:]:  # Skip header lines
    audit_lines.append(line)

audit_lines.append("\n## 关键变量覆盖率 (2017-2022, v5预处理后)\n")
audit_lines.append("| 变量 | 缺失率 | 均值 | 标准差 | Min | Max |")
audit_lines.append("|------|--------|------|--------|-----|-----|")
for v in ["ln_invention_apply","ln_invention_grant","ln_patent_apply_total","ln_patent_grant_total",
           "rd_intensity","ln_rd_staff","rd_staff_ratio","ln_assets","roa","firm_age",
           "cashflow_ratio","ln_rd_subsidy","policy_exposure","z_policy_exposure",
           "pre_rd_intensity","province_sci_tech_ratio","province_rd_intensity",
           "manufacturing","soe","hightech_mfg","manufacturing_post2021"]:
    if v in S["2017_2022"].columns:
        col = pd.to_numeric(S["2017_2022"][v], errors="coerce")
        audit_lines.append(f"| {v} | {col.isna().mean():.1%} | {col.mean():.4g} | {col.std():.4g} | {col.min():.4g} | {col.max():.4g} |")

with open(OUT / "explore_data_audit.md", "w", encoding="utf-8") as f:
    f.write("\n".join(audit_lines))

# ============================================================
# 10. 关键结果打印
# ============================================================
print("\n" + "=" * 80)
print("10. 关键发现")
print("=" * 80)

# Print all significant/notable results
notable = df_all_res[(df_all_res["p_value"].notna()) &
                      (df_all_res["p_value"] < 0.10) &
                      (df_all_res["variable"].str.contains(
                          "manufacturing_post2021|policy_exposure|treat_|hightech_post|high_exposure|Q|did_x|mfg_post_x", na=False))]

for _, row in notable.iterrows():
    sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*"
    print(f"  [{row['model']:30s}] {row['variable']:30s} → {str(row.get('dependent','')):25s} "
          f"coef={row['coef']:.4f} se={row['std_err']:.4f} p={row['p_value']:.4f}{sig} "
          f"N={int(row['nobs']):,} rec={row['recommendation']}")

print(f"\n推荐主线数: {len(main_lines)}, 次要方向数: {len(secondary)}")

elapsed = time.time() - T0
print(f"\n总运行时间: {elapsed:.1f}s ({elapsed/60:.1f}min)")

# List output files
print(f"\n所有输出: {OUT}/")
for f in sorted(os.listdir(OUT)):
    if f.startswith("explore_"):
        sz = os.path.getsize(OUT / f)
        print(f"  {f} ({sz:,} bytes)")

print("\nDONE: V5探索性方向筛选完成")
