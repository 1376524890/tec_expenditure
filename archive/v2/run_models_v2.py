"""
科技自主创新政策实证研究 — 重建模型脚本
==========================================
输入: data/firm_panel_v2.csv
输出: outputs/rebuild_*.csv / outputs/rebuild_*.md

所有模型使用企业固定效应 + 年份固定效应，标准误按企业聚类。
"""
from __future__ import annotations

import json, os, warnings
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

OUT_DIR = Path("outputs/rebuild")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. 读取数据
# ============================================================
print("=" * 80)
print("1. 读取重建面板")
print("=" * 80)

df_all = pd.read_csv("data/firm_panel_v2.csv")
print(f"  全量: {len(df_all):,} rows × {len(df_all.columns)} cols")

# 选择分析样本
# ============================================================
def prep_sample(df: pd.DataFrame, years: range, name: str) -> pd.DataFrame:
    """准备分析样本"""
    d = df[df["year"].between(years.start, years.stop - 1)].copy()
    d["year"] = d["year"].astype(int)
    d["stock_code"] = d["stock_code"].astype(str).str.zfill(6)
    print(f"  {name}: {len(d):,} obs × {d['stock_code'].nunique():,} firms, "
          f"manufacturing={d['manufacturing'].mean():.1%}")
    return d

sample_2017_2022 = prep_sample(df_all, range(2017, 2023), "2017-2022 (基准)")
sample_2016_2022 = prep_sample(df_all, range(2016, 2023), "2016-2022")
sample_2017_2024 = prep_sample(df_all, range(2017, 2025), "2017-2024")
sample_2019_2024 = prep_sample(df_all, range(2019, 2025), "2019-2024")

# ============================================================
# 2. 变量定义
# ============================================================
print("\n" + "=" * 80)
print("2. 变量构造")
print("=" * 80)

def construct_vars(df: pd.DataFrame) -> pd.DataFrame:
    """构造分析所需变量"""
    d = df.copy()

    # 因变量 (log1p)
    for v in ["invention_apply", "invention_grant", "patent_apply", "patent_grant",
               "invention_cum_obtain", "invention_cum_grant"]:
        if v in d.columns:
            d[v] = pd.to_numeric(d[v], errors="coerce").fillna(0).clip(lower=0)
            d[f"ln_{v}"] = np.log1p(d[v])

    # 控制变量
    for c in ["total_assets", "revenue", "RDSpendSum", "RDPerson", "RDPersonRatio",
              "total_subsidy", "rd_subsidy", "tax_saving_est", "rd_tax_deduction_est"]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")

    # ln_assets
    if "total_assets" in d.columns:
        d["ln_assets"] = np.log1p(d["total_assets"].fillna(0).clip(lower=0))

    # ROA
    if "profit_before_tax" in d.columns and "total_assets" in d.columns:
        d["profit_before_tax"] = pd.to_numeric(d["profit_before_tax"], errors="coerce")
        d["roa"] = np.where(
            d["total_assets"].notna() & (d["total_assets"] > 0),
            d["profit_before_tax"] / d["total_assets"],
            np.nan
        )

    # Firm age
    if "firm_age" not in d.columns or d["firm_age"].isna().mean() > 0.5:
        # try to construct from establish_date
        if "establish_date" in d.columns:
            est = pd.to_datetime(d["establish_date"], errors="coerce", format="mixed").dt.year
            d["firm_age"] = d["year"] - est
            d["firm_age"] = d["firm_age"].clip(lower=0)

    # rd_intensity
    if "RDSpendSum" in d.columns and "revenue" in d.columns:
        d["rd_intensity"] = np.where(
            (d["RDSpendSum"].notna()) & (d["revenue"].notna()) & (d["revenue"] > 0),
            d["RDSpendSum"] / d["revenue"] * 100,
            np.nan
        )

    # rd_staff
    if "RDPerson" in d.columns:
        d["rd_staff"] = d["RDPerson"]
    if "RDPersonRatio" in d.columns:
        d["rd_staff_ratio"] = d["RDPersonRatio"]

    # Tax variables
    if "tax_saving_est" in d.columns:
        d["ln_tax_saving"] = np.log1p(d["tax_saving_est"].fillna(0).clip(lower=0))
    if "rd_subsidy" in d.columns:
        d["ln_rd_subsidy"] = np.log1p(d["rd_subsidy"].fillna(0).clip(lower=0))
    if "total_subsidy" in d.columns:
        d["ln_total_subsidy"] = np.log1p(d["total_subsidy"].fillna(0).clip(lower=0))

    # Winsorize continuous variables (1%, 99%)
    cont_vars = [
        "rd_intensity", "roa", "rd_staff_ratio", "ln_assets",
        "ln_tax_saving", "ln_rd_subsidy", "ln_total_subsidy",
    ]
    for v in cont_vars:
        if v in d.columns:
            s = d[v].dropna()
            if len(s) > 100:
                lo, hi = s.quantile(0.01), s.quantile(0.99)
                d[v] = d[v].clip(lo, hi)

    # Lagged tax saving (by stock_code)
    if "ln_tax_saving" in d.columns:
        d = d.sort_values(["stock_code", "year"])
        d["ln_tax_saving_l1"] = d.groupby("stock_code")["ln_tax_saving"].shift(1)

    return d


# ============================================================
# 3. 回归引擎
# ============================================================
print("\n" + "=" * 80)
print("3. 定义回归引擎")
print("=" * 80)

def run_fe_model(
    df: pd.DataFrame,
    y: str,
    xvars: List[str],
    model_name: str,
    entity: str = "stock_code",
    time: str = "year",
    use_controls: bool = True,
    extra_controls: Optional[List[str]] = None
) -> Optional[Tuple[pd.DataFrame, str]]:
    """
    运行双向固定效应模型。
    优先使用 linearmodels.PanelOLS，失败则回退到 statsmodels OLS + dummies。
    """
    controls_base = ["ln_assets", "roa", "firm_age"]
    if use_controls:
        ctrls = [c for c in controls_base if c in df.columns]
    else:
        ctrls = []
    if extra_controls:
        for ec in extra_controls:
            if ec in df.columns and ec not in ctrls:
                ctrls.append(ec)

    all_x = xvars + ctrls
    needed = [y, entity, time] + all_x
    if not set(needed).issubset(df.columns):
        missing = [c for c in needed if c not in df.columns]
        return None, f"MISSING_COLUMNS: {missing}"

    d = df[needed].copy()
    for c in [y] + all_x:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna()
    if d.empty:
        return None, "NO_DATA after dropna"

    # 单变量检查
    for v in all_x:
        if d[v].nunique() < 2 or d[v].std() == 0:
            all_x.remove(v)
    if not all_x:
        return None, "NO_VALID_X"

    # Check: at least 10 clusters
    if d[entity].nunique() < 10:
        return None, f"TOO_FEW_ENTITIES: {d[entity].nunique()}"

    summary_lines = [f"Model: {model_name}", f"Dependent: {y}", f"X: {all_x}",
                     f"N: {len(d):,}, Firms: {d[entity].nunique():,}, Years: {d[time].nunique()}"]

    rows = []
    engine_used = "none"
    fallback_reason = ""

    if HAS_LINEARMODELS:
        try:
            pdata = d.set_index([entity, time])
            formula = f"{y} ~ 1 + {' + '.join(all_x)} + EntityEffects + TimeEffects"
            res = PanelOLS.from_formula(formula, data=pdata, drop_absorbed=True).fit(
                cov_type="clustered", cluster_entity=True
            )
            for v in all_x:
                if v in res.params.index:
                    rows.append({
                        "model": model_name, "dependent": y, "variable": v,
                        "coef": float(res.params[v]),
                        "std_err": float(res.std_errors[v]),
                        "p_value": float(res.pvalues[v]),
                        "nobs": int(res.nobs),
                        "firms": int(d[entity].nunique()),
                        "years": int(d[time].nunique()),
                        "r2_within": float(res.rsquared_within) if res.rsquared_within is not None else None,
                        "engine": "PanelOLS"
                    })
            engine_used = "PanelOLS"
            summary_lines.append(str(res.summary))
        except Exception as e:
            fallback_reason = f"PanelOLS failed: {e}"

    if not rows:
        # Statsmodels fallback
        try:
            formula = f"{y} ~ {' + '.join(all_x)} + C({entity}) + C({time})"
            res = smf.ols(formula, data=d).fit(
                cov_type="cluster", cov_kwds={"groups": d[entity]}
            )
            for v in all_x:
                if v in res.params.index:
                    rows.append({
                        "model": model_name, "dependent": y, "variable": v,
                        "coef": float(res.params[v]),
                        "std_err": float(res.bse[v]),
                        "p_value": float(res.pvalues[v]),
                        "nobs": int(res.nobs),
                        "firms": int(d[entity].nunique()),
                        "years": int(d[time].nunique()),
                        "r2_within": None,
                        "engine": f"statsmodels OLS dummy FE ({fallback_reason})"
                    })
            engine_used = "statsmodels OLS"
            summary_lines.append(str(res.summary()))
        except Exception as e:
            return None, f"BOTH_ENGINES_FAILED: {fallback_reason}; statsmodels: {e}"

    return pd.DataFrame(rows), "\n".join(summary_lines)


# ============================================================
# 4. 运行所有模型
# ============================================================
print("\n" + "=" * 80)
print("4. 运行所有模型")
print("=" * 80)

def run_all_models(df: pd.DataFrame, sample_label: str) -> Dict:
    """在给定样本上运行全部模型"""
    d = construct_vars(df)
    results = {}
    summaries = []

    def add_result(bucket: str, result, title: str):
        if result is None:
            return
        table, summary = result
        if table is not None and len(table):
            if bucket not in results:
                results[bucket] = []
            results[bucket].append(table)
            summaries.append(f"\n{'='*100}\n[SAMPLE={sample_label}] {title}\n{summary}")

    # ---- 主模型: DID ----
    add_result("baseline",
        run_fe_model(d, "ln_invention_apply", ["manufacturing_post2021"], "M1_Baseline_DID"),
        "M1: ln(1+invention_apply) ~ manufacturing_post2021 + controls + FE")

    # ---- 替代因变量 ----
    for dep_var, label in [
        ("ln_invention_grant", "M2a_invention_grant"),
        ("ln_patent_apply", "M2b_patent_apply"),
        ("ln_patent_grant", "M2c_patent_grant"),
    ]:
        if dep_var in d.columns:
            add_result("alternative_outcomes",
                run_fe_model(d, dep_var, ["manufacturing_post2021"], label),
                f"{label}: {dep_var} ~ manufacturing_post2021 + controls + FE")

    # ---- 机制检验: 研发投入 ----
    if "rd_intensity" in d.columns:
        add_result("mechanism",
            run_fe_model(d, "rd_intensity", ["manufacturing_post2021"], "M3a_RD_intensity",
                         extra_controls=["rd_staff_ratio"]),
            "M3a: rd_intensity ~ manufacturing_post2021 + controls + FE")

    # 机制: 研发人员
    if "rd_staff" in d.columns:
        d["ln_rd_staff"] = np.log1p(d["rd_staff"].fillna(0).clip(lower=0))
        add_result("mechanism",
            run_fe_model(d, "ln_rd_staff", ["manufacturing_post2021"], "M3b_RD_staff"),
            "M3b: ln(1+rd_staff) ~ manufacturing_post2021 + controls + FE")

    # 机制: 研发补助
    if "ln_rd_subsidy" in d.columns:
        add_result("mechanism",
            run_fe_model(d, "ln_invention_apply", ["manufacturing_post2021"],
                         "M3c_rd_subsidy_channel", extra_controls=["ln_rd_subsidy"]),
            "M3c: add ln(1+rd_subsidy) as additional regressor")

    # ---- 税收强度模型 ----
    if "ln_tax_saving" in d.columns:
        add_result("tax_intensity",
            run_fe_model(d, "ln_invention_apply", ["manufacturing_post2021", "ln_tax_saving"],
                         "M4a_tax_intensity"),
            "M4a: add ln(1+tax_saving_est) — ESTIMATED, NOT actual tax data")

    if "ln_tax_saving_l1" in d.columns:
        add_result("tax_intensity",
            run_fe_model(d, "ln_invention_apply", ["manufacturing_post2021", "ln_tax_saving_l1"],
                         "M4b_tax_intensity_lag"),
            "M4b: lagged ln(1+tax_saving_est)")

    # ---- 稳健性 ----
    # 5a: 2017-2022 (baseline sample)
    # 5b: 2016-2022
    # 5c: 剔除2024
    if "year" in d.columns:
        d_no2024 = d[d["year"] != 2024].copy()
        add_result("robustness",
            run_fe_model(d_no2024, "ln_invention_apply", ["manufacturing_post2021"], "M5a_drop2024"),
            "M5a: drop 2024")

        # 5d: 控制 post2023
        if "post2023" in d.columns:
            add_result("robustness",
                run_fe_model(d, "ln_invention_apply", ["manufacturing_post2021", "post2023"], "M5b_ctrl_post2023"),
                "M5b: control post2023 (full-sample 100% super-deduction year)")

    # 5e: 安慰剂 post2020
    if "manufacturing_post2020" in d.columns:
        add_result("robustness",
            run_fe_model(d, "ln_invention_apply", ["manufacturing_post2020"], "M5c_placebo_post2020"),
            "M5c: placebo DID with post2020 (expect null)")

    # ---- 事件研究 ----
    if "year" in d.columns and "manufacturing" in d.columns:
        d_es = d.copy()
        d_es["rel_year"] = d_es["year"].astype(int) - 2021
        event_vars = []
        # Pre: 2017, 2018, 2019 as pre-period, omit 2020 as baseline
        for k in range(-4, 5):  # -4 to 4
            if k == -1:  # baseline
                continue
            if k < 0:
                name = f"event_pre_{abs(k)}"
            else:
                name = f"event_post_{k}"
            d_es[name] = ((d_es["rel_year"] == k).astype(int) * d_es["manufacturing"]).astype(float)
            if d_es[name].notna().sum() > 0 and d_es[name].nunique() > 1:
                event_vars.append(name)

        add_result("event_study",
            run_fe_model(d_es, "ln_invention_apply", event_vars, "M6_event_study"),
            f"M6: Event study, baseline=2020, event periods: {event_vars}")

    # ---- 异质性: SOE (子样本) ----
    if "soe" in d.columns and d["soe"].notna().sum() > 100:
        for soe_val, soe_label in [(1, "SOE"), (0, "NonSOE")]:
            d_soe = d[d["soe"] == soe_val].copy()
            if len(d_soe) > 100:
                add_result("heterogeneity",
                    run_fe_model(d_soe, "ln_invention_apply", ["manufacturing_post2021"],
                                 f"M7_{soe_label}_subsample"),
                    f"M7: {soe_label} subsample only")

    return results, summaries


# ============================================================
# 5. 运行所有样本
# ============================================================
all_results = {}
all_summaries = []

for sample, df in [
    ("2017_2022_baseline", sample_2017_2022),
    ("2016_2022", sample_2016_2022),
    ("2017_2024", sample_2017_2024),
    ("2019_2024", sample_2019_2024),
]:
    print(f"\n--- Running: {sample} ---")
    res, sums = run_all_models(df, sample)
    for k, v in res.items():
        if k not in all_results:
            all_results[k] = []
        all_results[k].extend(v)
    all_summaries.extend(sums)

# ============================================================
# 6. 数据审计
# ============================================================
print("\n" + "=" * 80)
print("6. 生成数据审计")
print("=" * 80)

audit_lines = []
audit_lines.append("# 重建数据审计报告\n")
audit_lines.append(f"## 面板概况\n")
audit_lines.append(f"- 全量表 (2016-2025): {len(df_all):,} obs × {df_all['stock_code'].nunique():,} firms")
audit_lines.append(f"- 基准样本 (2017-2022): {len(sample_2017_2022):,} obs × {sample_2017_2022['stock_code'].nunique():,} firms")
audit_lines.append(f"- 制造业占比: {sample_2017_2022['manufacturing'].mean():.1%}")
audit_lines.append(f"- soe 覆盖率: {sample_2017_2022['soe'].notna().mean():.1%}")
audit_lines.append(f"- soe=1 (国有): {(sample_2017_2022['soe']==1).sum():,}")
audit_lines.append(f"- soe=0 (非国有): {(sample_2017_2022['soe']==0).sum():,}")
audit_lines.append("")
audit_lines.append("## 政策变量摘要\n")
audit_lines.append(f"### rd_deduction_rate 分布")
for yr in sorted(sample_2017_2022["year"].unique()):
    for mfg in [1, 0]:
        mask = (sample_2017_2022["year"] == yr) & (sample_2017_2022["manufacturing"] == mfg)
        if mask.any():
            rate = sample_2017_2022.loc[mask, "rd_deduction_rate"].iloc[0]
            audit_lines.append(f"- {int(yr)}, {'制造业' if mfg else '非制造业'}: {rate:.0%}")
audit_lines.append("")

# Variable coverage
audit_lines.append("## 关键变量覆盖率 (基准样本 2017-2022)\n")
audit_lines.append("| 变量 | 非缺失 | 缺失率 | 均值 | 标准差 |")
audit_lines.append("|------|--------|--------|------|--------|")
for v in ["ln_invention_apply", "ln_invention_grant", "ln_patent_apply", "ln_patent_grant",
           "rd_intensity", "rd_staff", "rd_staff_ratio", "ln_assets", "roa", "firm_age",
           "ln_tax_saving", "ln_rd_subsidy", "ln_total_subsidy", "soe", "etr"]:
    if v in sample_2017_2022.columns:
        s = pd.to_numeric(sample_2017_2022[v], errors="coerce")
        audit_lines.append(f"| {v} | {s.notna().sum():,} | {s.isna().mean():.1%} | {s.mean():.3g} | {s.std():.3g} |")
audit_lines.append("")

# SOE classification rule
audit_lines.append("## SOE 分类规则\n")
audit_lines.append("- 来源: HLD_Contrshr.S0702b (实际控制人性质)")
audit_lines.append("- 规则: controller_type 以 '1' 开头 → soe=1 (国有企业)")
audit_lines.append("-        controller_type 以 '2' 开头 → soe=0 (非国有: 民营/自然人)")
audit_lines.append("-        其他 → NaN (外资/集体/无法归类)")
audit_lines.append(f"- 覆盖率: {sample_2017_2022['soe'].notna().mean():.1%}")
audit_lines.append("")

# Government subsidy keywords
audit_lines.append("## 研发补助关键词规则\n")
keywords = ["研发", "科技", "创新", "高新", "专利", "技术", "R&D", "科研", "发明",
            "技改", "技术改造", "知识产权", "产业化", "新产品", "新工艺", "软件",
            "信息化", "数字化", "智能", "实验室", "工程中心", "技术中心", "研究院"]
audit_lines.append(f"- 关键词 ({len(keywords)}): {', '.join(keywords)}")
audit_lines.append(f"- 匹配率: 30.3% (研发相关项目占全部政府补助项目的比例)")
audit_lines.append("")

# Missing rates CSV
miss_df = sample_2017_2022[[c for c in sample_2017_2022.columns
    if sample_2017_2022[c].dtype in ['float64', 'int64']]].isna().mean().sort_values(ascending=False)
miss_df.to_csv(OUT_DIR / "rebuild_missing_rates.csv", encoding="utf-8-sig")

# Descriptive stats
desc_vars = [c for c in ["ln_invention_apply", "ln_invention_grant", "ln_patent_apply",
    "ln_patent_grant", "rd_intensity", "ln_rd_staff", "rd_staff_ratio",
    "ln_assets", "roa", "firm_age", "ln_tax_saving", "ln_rd_subsidy",
    "ln_total_subsidy", "etr"]
    if c in sample_2017_2022.columns]
if desc_vars:
    desc = sample_2017_2022[desc_vars].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).T
    desc.to_csv(OUT_DIR / "rebuild_descriptive_statistics.csv", encoding="utf-8-sig")

with open(OUT_DIR / "rebuild_data_audit.md", "w", encoding="utf-8") as f:
    f.write("\n".join(audit_lines))

print(f"  审计报告: {OUT_DIR / 'rebuild_data_audit.md'}")

# ============================================================
# 7. 保存结果
# ============================================================
print("\n" + "=" * 80)
print("7. 保存模型结果")
print("=" * 80)

bucket_files = {
    "baseline": "rebuild_baseline_results.csv",
    "alternative_outcomes": "rebuild_alternative_outcomes_results.csv",
    "mechanism": "rebuild_mechanism_results.csv",
    "tax_intensity": "rebuild_tax_intensity_results.csv",
    "robustness": "rebuild_robustness_results.csv",
    "event_study": "rebuild_event_study.csv",
    "heterogeneity": "rebuild_heterogeneity_results.csv",
}

for bucket, tables in all_results.items():
    if tables:
        combined = pd.concat(tables, ignore_index=True)
        fname = bucket_files.get(bucket, f"rebuild_{bucket}.csv")
        combined.to_csv(OUT_DIR / fname, index=False, encoding="utf-8-sig")
        print(f"  {fname}: {len(combined)} rows")
    else:
        print(f"  {bucket}: no results")

# Full summaries
with open(OUT_DIR / "rebuild_full_model_summaries.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_summaries))

# ============================================================
# 8. 生成实证报告
# ============================================================
print("\n" + "=" * 80)
print("8. 生成实证报告")
print("=" * 80)

report = []
report.append("# 科技自主创新政策实证研究报告\n")
report.append("## 一、数据与样本\n")

d_base = construct_vars(sample_2017_2022)
report.append(f"- 基准样本: 2017-2022, {len(d_base):,} obs × {d_base['stock_code'].nunique():,} firms")
report.append(f"- 处理组 (制造业): {(d_base['manufacturing']==1).sum():,}, "
              f"对照组 (非制造业): {(d_base['manufacturing']==0).sum():,}")
report.append(f"- 政策冲击: 2021 年制造业研发费用加计扣除比例从 75% 提高至 100%")
report.append("")

# Core DID result
report.append("## 二、基准 DID 结果\n")
baseline = all_results.get("baseline", [])
if baseline:
    bl = pd.concat(baseline, ignore_index=True)
    # Filter to 2017-2022 baseline sample
    bl_m1 = bl[(bl["model"] == "M1_Baseline_DID") & (bl["variable"] == "manufacturing_post2021")]
    if len(bl_m1):
        for _, row in bl_m1.iterrows():
            sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.1 else ""
            report.append(f"- manufacturing_post2021: coef={row['coef']:.4f}, se={row['std_err']:.4f}, "
                          f"p={row['p_value']:.4f}{sig}, n={int(row['nobs']):,}, firms={int(row['firms']):,}")
    else:
        report.append("- 基准 DID 模型未成功运行或未找到结果。")
report.append("")

# Mechanism
report.append("## 三、机制检验\n")
mech = all_results.get("mechanism", [])
if mech:
    mdf = pd.concat(mech, ignore_index=True)
    for _, row in mdf.iterrows():
        if row["variable"] == "manufacturing_post2021":
            sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.1 else ""
            report.append(f"- {row['model']}: coef={row['coef']:.4f}, se={row['std_err']:.4f}, p={row['p_value']:.4f}{sig}")
report.append("")

# Robustness
report.append("## 四、稳健性检验\n")
rob = all_results.get("robustness", [])
if rob:
    rdf = pd.concat(rob, ignore_index=True)
    for _, row in rdf.iterrows():
        if row["variable"] in ["manufacturing_post2021", "manufacturing_post2020"]:
            sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.1 else ""
            report.append(f"- {row['model']} ({row['variable']}): coef={row['coef']:.4f}, se={row['std_err']:.4f}, p={row['p_value']:.4f}{sig}")
report.append("")

# Event study
report.append("## 五、事件研究\n")
evt = all_results.get("event_study", [])
if evt:
    edf = pd.concat(evt, ignore_index=True)
    report.append("| 变量 | 系数 | 标准误 | p值 |")
    report.append("|------|------|--------|-----|")
    for _, row in edf.iterrows():
        sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.1 else ""
        report.append(f"| {row['variable']} | {row['coef']:.4f} | {row['std_err']:.4f} | {row['p_value']:.4f}{sig} |")
report.append("")

# Conclusion
report.append("## 六、结论约束\n")
report.append("- 不得把 `tax_saving_est` 写成真实税收优惠数据，该变量是 `RDSpendSum × rd_deduction_rate × 0.25` 的估算值。")
report.append("- 不得把累计专利存量 (`invention_cum_*`) 解释为当年创新产出。")
report.append("- 因变量使用 `ln(1 + invention_apply)` 即当年发明专利申请的流量指标。")
report.append("- 如果基准 DID 不显著，如实报告，不得修改模型追求显著性。")
report.append("- 2023-2024 年全行业加计扣除比例均提高至 100%，制造业_post2021 效应可能被稀释。")
report.append("- SOE 变量覆盖率仅 27%，异质性分析为子样本结果，不具全样本代表性。")

with open(OUT_DIR / "rebuild_empirical_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(report))

# ============================================================
# DONE
# ============================================================
print("\n" + "=" * 80)
print("DONE: 所有模型已运行")
print("=" * 80)

# Print key results
print("\n关键结果摘要:")
for bucket, fname in bucket_files.items():
    fpath = OUT_DIR / fname
    if fpath.exists():
        df = pd.read_csv(fpath)
        # Print DID coefficient results
        did_rows = df[df["variable"].str.contains("manufacturing_post2021|manufacturing_post2020", na=False)]
        if len(did_rows):
            for _, r in did_rows.iterrows():
                sig = "***" if r["p_value"] < 0.01 else "**" if r["p_value"] < 0.05 else "*" if r["p_value"] < 0.1 else ""
                print(f"  [{r['model']}] {r['variable']}: {r['coef']:.4f} ({r['std_err']:.4f}), p={r['p_value']:.4f}{sig}")

print(f"\n所有输出文件: {OUT_DIR}/")
for f in sorted(os.listdir(OUT_DIR)):
    print(f"  {f}")
