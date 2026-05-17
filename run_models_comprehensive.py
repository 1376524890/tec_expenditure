"""
科技自主创新政策实证研究 — 综合模型分析 (Comprehensive)
========================================================
全面覆盖: 基准DID、替代因变量、PPML、政策阶段比较、政策暴露强度、
高低研发基础分组、高技术制造业异质性、机制检验、省级财政交互、
事件研究、安慰剂检验、PSM-DID

输入: data/firm_panel_v4.csv
输出: outputs/final/
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

OUT = Path("outputs/final")
OUT.mkdir(parents=True, exist_ok=True)

T0 = time.time()

# ============================================================
# 0. GPU detection
# ============================================================
try:
    import subprocess
    gpu_info = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=5)
    if gpu_info.returncode == 0:
        print(f"GPU: {gpu_info.stdout.strip()}")
    else:
        print("GPU: 无 NVIDIA GPU (使用 CPU)")
except Exception:
    print("GPU: 无法检测")

# ============================================================
# 1. 读取和准备数据
# ============================================================
print("=" * 80)
print("1. 读取和准备数据")
print("=" * 80)

df_all = pd.read_csv("data/firm_panel_v4.csv")
df_all["stock_code"] = df_all["stock_code"].astype(str).str.zfill(6)
df_all["year"] = df_all["year"].astype(int)

# Fix province_sci_tech_ratio (already float64 but let's ensure numeric)
for v in ["province_sci_tech_ratio", "province_rd_intensity", "province_sci_tech_exp",
          "ln_province_sci_tech_exp", "ln_province_gdp", "ln_province_fiscal_exp",
          "ln_province_rd_expenditure", "ln_province_tech_market"]:
    if v in df_all.columns:
        df_all[v] = pd.to_numeric(df_all[v], errors="coerce")

# ============================================================
# 1a. 构造缺失的变量
# ============================================================
print("\n构造缺失变量...")

# 政策阶段变量
df_all["treat_2021_2022"] = df_all["manufacturing"] * ((df_all["year"] >= 2021) & (df_all["year"] <= 2022)).astype(int)
df_all["treat_2023_2024"] = df_all["manufacturing"] * (df_all["year"] >= 2023).astype(int)
print(f"  treat_2021_2022: mean={df_all['treat_2021_2022'].mean():.3f}")
print(f"  treat_2023_2024: mean={df_all['treat_2023_2024'].mean():.3f}")

# 高技术制造业识别
# 基于国家统计局《高技术产业(制造业)分类(2017)》
# CSMAR industry_code 对应: C27(医药), C26(化学), C34-C40(设备), C39(计算机通信), C40(仪器仪表)
# 更广义: 医药制造C27, 航空C37, 航天C37, 电子C39, 计算机C39, 通信C39, 医疗C35, 仪器C40
HIGHTECH_CODES = [
    "C27",  # 医药制造业
    "C37",  # 铁路船舶航空航天
    "C38",  # 电气机械和器材
    "C39",  # 计算机通信和其他电子设备
    "C40",  # 仪器仪表制造业
    "C26",  # 化学原料和化学制品 (含部分高技术)
    "C34",  # 通用设备
    "C35",  # 专用设备
]
# 狭义高技术制造业 (按国家统计局标准)
HIGHTECH_NARROW = ["C27", "C37", "C38", "C39", "C40"]

df_all["hightech_manufacturing"] = 0
mask_ht = df_all["industry_code"].astype(str).str[:3].isin(HIGHTECH_CODES) & (df_all["manufacturing"] == 1)
df_all.loc[mask_ht, "hightech_manufacturing"] = 1
print(f"  hightech_manufacturing: {df_all['hightech_manufacturing'].sum():,} obs, "
      f"{df_all[df_all['manufacturing']==1]['hightech_manufacturing'].mean():.1%} of manufacturing")

# 狭义高技术
df_all["hightech_narrow"] = 0
mask_htn = df_all["industry_code"].astype(str).str[:3].isin(HIGHTECH_NARROW) & (df_all["manufacturing"] == 1)
df_all.loc[mask_htn, "hightech_narrow"] = 1
print(f"  hightech_narrow: {df_all['hightech_narrow'].sum():,} obs")

# 高技术 × post2021
df_all["hightech_post2021"] = df_all["hightech_manufacturing"] * df_all["post2021"]
df_all["hightech_narrow_post2021"] = df_all["hightech_narrow"] * df_all["post2021"]

# 高/低研发基础分组 (基于 pre_rd_intensity 中位数)
median_pre_rd = df_all.loc[df_all["year"].between(2017, 2020), "pre_rd_intensity"].median()
df_all["high_pre_rd"] = (df_all["pre_rd_intensity"] > median_pre_rd).astype(int)
df_all.loc[df_all["pre_rd_intensity"].isna(), "high_pre_rd"] = np.nan
print(f"  pre_rd_intensity 中位数: {median_pre_rd:.4f}")
print(f"  high_pre_rd=1: {(df_all['high_pre_rd']==1).sum():,}, high_pre_rd=0: {(df_all['high_pre_rd']==0).sum():,}")

# ============================================================
# 1b. 数据结构审计
# ============================================================
print("\n" + "=" * 80)
print("数据结构审计")
print("=" * 80)

# Full sample
dup_all = df_all.duplicated(subset=["stock_code", "year"]).sum()
print(f"全样本 (2016-2025): {len(df_all):,} obs, {df_all['stock_code'].nunique():,} firms, dup={dup_all}")

# Subsamples
samples = {}
for yr_start, yr_end, label in [
    (2017, 2022, "2017-2022 (基准)"),
    (2017, 2024, "2017-2024 (扩展)"),
    (2017, 2020, "2017-2020 (安慰剂)"),
    (2016, 2022, "2016-2022"),
]:
    s = df_all[df_all["year"].between(yr_start, yr_end)].copy()
    dup = s.duplicated(subset=["stock_code", "year"]).sum()
    max_obs = s.groupby("stock_code").size().max()
    expected = yr_end - yr_start + 1
    firms_over = (s.groupby("stock_code").size() > expected).sum()
    print(f"  {label}: {len(s):,} obs, {s['stock_code'].nunique():,} firms, "
          f"dup={dup}, max_obs={max_obs}, firms_exceeding={firms_over}, "
          f"mfg={s['manufacturing'].mean():.1%}")
    samples[label] = s

S_2017_2022 = samples["2017-2022 (基准)"]
S_2017_2024 = samples["2017-2024 (扩展)"]
S_2017_2020 = samples["2017-2020 (安慰剂)"]
S_2016_2022 = samples["2016-2022"]

# Critical check
assert dup_all == 0, f"FATAL: Full sample has {dup_all} duplicates!"
for label, s in samples.items():
    dup = s.duplicated(subset=["stock_code", "year"]).sum()
    assert dup == 0, f"FATAL: {label} has {dup} duplicates!"

print("\n>>> 最终面板为唯一企业年度面板，不存在 stock_code-year 重复观测。 <<<")

# ============================================================
# 2. 回归引擎
# ============================================================
print("\n" + "=" * 80)
print("2. 回归引擎")
print("=" * 80)


def run_fe(df_in, y, xvars, name, extra_ctrl=None, cluster_by="stock_code"):
    """
    双向固定效应: entity + year FE, clustered by entity.
    优先 linearmodels.PanelOLS, 回退 statsmodels OLS + dummies.
    """
    ctrls_base = ["ln_assets", "roa", "cashflow_ratio", "firm_age"]
    ctrls = [c for c in ctrls_base if c in df_in.columns]
    if extra_ctrl:
        ctrls.extend([c for c in extra_ctrl if c in df_in.columns and c not in ctrls])

    all_x = xvars + ctrls
    needed = ["stock_code", "year", y] + all_x
    missing_cols = [c for c in needed if c not in df_in.columns]
    if missing_cols:
        return None, f"MISSING: {missing_cols}"

    d = df_in[needed].copy()
    for c in [y] + all_x:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna()
    if d.empty or d["stock_code"].nunique() < 10:
        return None, "NO_DATA"

    # Remove variables with no variation
    valid_x = [v for v in all_x if d[v].std() > 0 and d[v].nunique() > 1]
    if not valid_x:
        return None, "NO_VALID_X"

    rows = []
    summary = ""
    fallback = ""

    if HAS_LINEARMODELS:
        try:
            pdata = d.set_index(["stock_code", "year"])
            formula = f"{y} ~ 1 + {' + '.join(valid_x)} + EntityEffects + TimeEffects"
            res = PanelOLS.from_formula(formula, data=pdata, drop_absorbed=True).fit(
                cov_type="clustered", cluster_entity=True
            )
            for v in valid_x:
                if v in res.params.index:
                    rows.append(dict(model=name, dependent=y, variable=v,
                        coef=float(res.params[v]), std_err=float(res.std_errors[v]),
                        p_value=float(res.pvalues[v]), nobs=int(res.nobs),
                        firms=int(d["stock_code"].nunique()),
                        years=int(d["year"].nunique()),
                        r2_within=float(res.rsquared_within) if res.rsquared_within else None,
                        engine="PanelOLS"))
            summary = str(res.summary)

            # Wald test for event study joint
            ev_names = [v for v in valid_x if v.startswith("event_")]
            if len(ev_names) > 1:
                try:
                    wald = res.wald_test(formula=", ".join(ev_names))
                    rows.append(dict(model=name, dependent=y, variable="JOINT_TEST_EVENT",
                        coef=float(wald.stat), std_err=None, p_value=float(wald.pval),
                        nobs=int(res.nobs), firms=None, years=None, r2_within=None,
                        engine=f"Wald chi2, df={len(ev_names)}"))
                except Exception:
                    pass

            # Wald test for pre-trend joint test (event_2017, event_2018, event_2019)
            pre_ev_names = [v for v in ev_names if "m" in v or "2017" in v or "2018" in v or "2019" in v]
            if len(pre_ev_names) > 1:
                try:
                    wald_pre = res.wald_test(formula=", ".join(pre_ev_names))
                    rows.append(dict(model=name, dependent=y, variable="JOINT_TEST_PRE_TREND",
                        coef=float(wald_pre.stat), std_err=None, p_value=float(wald_pre.pval),
                        nobs=int(res.nobs), firms=None, years=None, r2_within=None,
                        engine=f"Wald chi2 (pre-trend), df={len(pre_ev_names)}"))
                except Exception:
                    pass

            # Wald test for stage policy comparison
            if "treat_2021_2022" in valid_x and "treat_2023_2024" in valid_x:
                try:
                    wald_stage = res.wald_test(formula="treat_2021_2022 = treat_2023_2024")
                    rows.append(dict(model=name, dependent=y, variable="WALD_STAGE_EQ",
                        coef=float(wald_stage.stat), std_err=None, p_value=float(wald_stage.pval),
                        nobs=int(res.nobs), firms=None, years=None, r2_within=None,
                        engine="Wald chi2, df=1"))
                except Exception:
                    pass

            return pd.DataFrame(rows), summary
        except Exception as e:
            fallback = str(e)[:200]

    # Fallback: OLS with dummies
    if not rows:
        try:
            formula = f"{y} ~ {' + '.join(valid_x)} + C(stock_code) + C(year)"
            res = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": d["stock_code"]})
            for v in valid_x:
                if v in res.params.index:
                    rows.append(dict(model=name, dependent=y, variable=v,
                        coef=float(res.params[v]), std_err=float(res.bse[v]),
                        p_value=float(res.pvalues[v]), nobs=int(res.nobs),
                        firms=int(d["stock_code"].nunique()),
                        years=int(d["year"].nunique()),
                        r2_within=None,
                        engine=f"OLS dummy FE"))
            summary = str(res.summary())

            # Wald test for event study
            ev_names = [v for v in valid_x if v.startswith("event_")]
            if len(ev_names) > 1:
                try:
                    wald = res.wald_test(",".join(ev_names), use_f=True)
                    rows.append(dict(model=name, dependent=y, variable="JOINT_TEST_EVENT",
                        coef=float(wald.statistic), std_err=None, p_value=float(wald.pvalue),
                        nobs=int(len(d)), firms=None, years=None, r2_within=None,
                        engine=f"Wald F, df={len(ev_names)}"))
                except Exception:
                    pass
        except Exception as e:
            return None, f"BOTH_FAILED: {fallback}; {e}"

    return pd.DataFrame(rows), summary


def generate_ppml_code(df_in, y, xvars, name, extra_ctrl=None):
    """Generate R and Stata code for PPML estimation.
    Python statsmodels GLM + dummies is too memory-intensive for ~5400 firm dummies.
    R fixest::fepois and Stata ppmlhdfe are the recommended tools.
    """
    ctrls_base = ["ln_assets", "roa", "cashflow_ratio", "firm_age"]
    ctrls = [c for c in ctrls_base if c in df_in.columns]
    if extra_ctrl:
        ctrls.extend([c for c in extra_ctrl if c in df_in.columns and c not in ctrls])
    all_x = xvars + ctrls

    d = df_in[["stock_code", "year", y] + all_x].copy()
    for c in [y] + all_x:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna()
    n_obs = len(d)
    n_firms = d["stock_code"].nunique()

    r_code = f"""
# R code for {name}
library(fixest)
df <- read.csv("data/firm_panel_v4.csv")
df_2017_2022 <- subset(df, year >= 2017 & year <= 2022)

m_{name} <- fepois(
  {y} ~ {' + '.join(all_x)} | stock_code + year,
  cluster = ~ stock_code,
  data = df_2017_2022
)
summary(m_{name})
"""
    stata_code = f"""
* Stata code for {name}
* import delimited data/firm_panel_v4.csv
* keep if year >= 2017 & year <= 2022
* ppmlhdfe {y} {' '.join(all_x)}, absorb(stock_code year) cluster(stock_code)
"""

    rows = [dict(model=name, dependent=y, variable=v,
        coef=None, std_err=None, p_value=None, nobs=n_obs,
        firms=n_firms, years=int(d["year"].nunique()),
        r2_within=None, engine="PPML (需 R fixest 或 Stata ppmlhdfe)") for v in xvars]

    return pd.DataFrame(rows), f"R code:\n{r_code}\n\nStata code:\n{stata_code}"


# ============================================================
# 3. 运行所有模型
# ============================================================
print("\n" + "=" * 80)
print("3. 运行所有模型")
print("=" * 80)

all_results = {}  # bucket -> list of DataFrames
all_summaries = []


def save_result(bucket, df_result):
    if df_result is not None and len(df_result) > 0:
        if bucket not in all_results:
            all_results[bucket] = []
        all_results[bucket].append(df_result)


def model_label(sample_name, model_name):
    return f"{model_name}"


# ============================================================
# M1: 基准 DID (2017-2022)
# ============================================================
print("\n--- M1: 基准 DID (2017-2022) ---")
res, summary = run_fe(S_2017_2022, "ln_invention_apply", ["manufacturing_post2021"],
                      "M1_Baseline_DID_2017_2022")
save_result("baseline", res)
all_summaries.append(f"\n{'='*100}\nM1: 基准 DID 2017-2022\n{summary}")

# ============================================================
# M1b: 基准 DID (2017-2024) - with post2023 control
# ============================================================
print("\n--- M1b: 基准 DID (2017-2024) with post2023 ---")
res, summary = run_fe(S_2017_2024, "ln_invention_apply",
                      ["manufacturing_post2021", "post2023"],
                      "M1b_DID_2017_2024_ctrl_post2023")
save_result("baseline", res)
all_summaries.append(f"\n{'='*100}\nM1b: 基准 DID 2017-2024 + post2023\n{summary}")

# ============================================================
# M3: 替代因变量稳健性 (2017-2022)
# ============================================================
print("\n--- M3: 替代因变量 (2017-2022) ---")
for dep, mdl in [
    ("ln_invention_grant", "M3a_Invention_Grant"),
    ("ln_patent_apply_total", "M3b_Patent_Apply_Total"),
    ("ln_patent_grant_total", "M3c_Patent_Grant_Total"),
]:
    res, summary = run_fe(S_2017_2022, dep, ["manufacturing_post2021"], mdl)
    save_result("robustness_alt_dv", res)
    all_summaries.append(f"\n{'='*100}\n{mdl}: {dep}\n{summary}")

# ============================================================
# M3d: 替代因变量 (2017-2024)
# ============================================================
print("\n--- M3d: 替代因变量 (2017-2024) ---")
for dep, mdl in [
    ("ln_invention_grant", "M3d_Grant_2017_2024"),
    ("ln_patent_apply_total", "M3e_Patent_Apply_2017_2024"),
    ("ln_patent_grant_total", "M3f_Patent_Grant_2017_2024"),
]:
    res, summary = run_fe(S_2017_2024, dep, ["manufacturing_post2021"], mdl)
    save_result("robustness_alt_dv", res)
    all_summaries.append(f"\n{'='*100}\n{mdl}: {dep}\n{summary}")

# ============================================================
# M4: PPML 计数模型 (2017-2022) — 生成 R/Stata 代码
# ============================================================
print("\n--- M4: PPML (2017-2022) — 生成R/Stata代码 ---")
ppml_codes = []
for dep, mdl in [
    ("invention_apply", "M4a_PPML_Invention_Apply"),
    ("invention_grant", "M4b_PPML_Invention_Grant"),
    ("patent_apply_total", "M4c_PPML_Patent_Apply"),
    ("patent_grant_total", "M4d_PPML_Patent_Grant"),
]:
    res, summary = generate_ppml_code(S_2017_2022, dep, ["manufacturing_post2021"], mdl)
    if res is not None:
        save_result("ppml", res)
        ppml_codes.append(f"\n{'='*100}\n{mdl}: PPML {dep}\n{summary}")
        print(f"  {mdl}: generated R/Stata code (N={int(res['nobs'].iloc[0]):,})")

# Save PPML code separately
with open(OUT / "ppml_r_stata_code.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(ppml_codes))
all_summaries.extend(ppml_codes)

# ============================================================
# M5: 政策阶段模型 (2017-2024)
# ============================================================
print("\n--- M5: 政策阶段模型 (2017-2024) ---")
res, summary = run_fe(S_2017_2024, "ln_invention_apply",
                      ["treat_2021_2022", "treat_2023_2024"],
                      "M5_Stage_Policy")
save_result("stage_policy", res)
all_summaries.append(f"\n{'='*100}\nM5: 政策阶段模型 2017-2024\n{summary}")

# Also run on 2017-2022 for comparison
res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                      ["treat_2021_2022"],
                      "M5b_Stage_2017_2022")
save_result("stage_policy", res)

# ============================================================
# M6: 政策暴露强度 (2017-2022 and 2017-2024)
# ============================================================
print("\n--- M6: 政策暴露强度 ---")
for sample, sname in [(S_2017_2022, "M6a_Exposure_2017_2022"),
                       (S_2017_2024, "M6b_Exposure_2017_2024")]:
    # Model with policy_exposure only (manufacturing_post2021 absorbed or not)
    res, summary = run_fe(sample, "ln_invention_apply",
                          ["manufacturing_post2021", "policy_exposure"],
                          sname)
    save_result("policy_exposure", res)
    all_summaries.append(f"\n{'='*100}\n{sname}: policy_exposure\n{summary}")

# ============================================================
# M7: 高低研发基础分组 (2017-2022)
# ============================================================
print("\n--- M7: 高低研发基础分组 ---")
for hv, hl in [(1, "M7a_High_Pre_RD"), (0, "M7b_Low_Pre_RD")]:
    d_sub = S_2017_2022[S_2017_2022["high_pre_rd"] == hv].copy()
    if len(d_sub) > 100:
        res, summary = run_fe(d_sub, "ln_invention_apply", ["manufacturing_post2021"],
                              f"{hl}_2017_2022")
        save_result("heterogeneity_pre_rd", res)
        all_summaries.append(f"\n{'='*100}\n{hl}: {'高' if hv==1 else '低'}研发基础\n{summary}")

# Also 2017-2024
for hv, hl in [(1, "M7c_High_Pre_RD_2017_2024"), (0, "M7d_Low_Pre_RD_2017_2024")]:
    d_sub = S_2017_2024[S_2017_2024["high_pre_rd"] == hv].copy()
    if len(d_sub) > 100:
        res, summary = run_fe(d_sub, "ln_invention_apply", ["manufacturing_post2021"],
                              hl)
        save_result("heterogeneity_pre_rd", res)

# ============================================================
# M8: 高技术制造业异质性
# ============================================================
print("\n--- M8: 高技术制造业异质性 ---")
# Model 1: hightech_manufacturing × post2021 (全样本)
res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                      ["hightech_post2021"], "M8a_Hightech_x_Post2021",
                      extra_ctrl=["hightech_manufacturing"])
save_result("heterogeneity_hightech", res)

# Model 1b: 狭义高技术
res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                      ["hightech_narrow_post2021"], "M8b_HightechNarrow_x_Post2021",
                      extra_ctrl=["hightech_narrow"])
save_result("heterogeneity_hightech", res)

# Model 2: 仅在制造业样本中比较
d_mfg = S_2017_2022[S_2017_2022["manufacturing"] == 1].copy()
if len(d_mfg) > 100:
    res, summary = run_fe(d_mfg, "ln_invention_apply",
                          ["hightech_post2021"], "M8c_MFG_Only_Hightech",
                          extra_ctrl=["hightech_manufacturing"])
    save_result("heterogeneity_hightech", res)

# 2017-2024 versions
res, summary = run_fe(S_2017_2024, "ln_invention_apply",
                      ["hightech_post2021"], "M8d_Hightech_2017_2024",
                      extra_ctrl=["hightech_manufacturing"])
save_result("heterogeneity_hightech", res)

# ============================================================
# M9: 机制检验
# ============================================================
print("\n--- M9: 机制检验 ---")

# M9a: 研发投入强度机制 (rd_intensity as DV)
res, summary = run_fe(S_2017_2022, "rd_intensity", ["manufacturing_post2021"],
                      "M9a_RD_Intensity_Mechanism")
save_result("mechanism", res)

# M9b: 研发人员机制
res, summary = run_fe(S_2017_2022, "ln_rd_staff", ["manufacturing_post2021"],
                      "M9b_RD_Staff_Mechanism")
save_result("mechanism", res)

# M9c: 研发补助协同 (含交互项)
res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                      ["manufacturing_post2021", "ln_rd_subsidy",
                       "manufacturing_post2021_x_ln_rd_subsidy"],
                      "M9c_Subsidy_Interaction",
                      extra_ctrl=["ln_rd_subsidy"])
# If subsidy interaction not in data, construct it
if res is None and "MISSING" in str(summary):
    S_2017_2022["manufacturing_post2021_x_ln_rd_subsidy"] = (
        S_2017_2022["manufacturing_post2021"] * S_2017_2022["ln_rd_subsidy"]
    )
    S_2017_2024["manufacturing_post2021_x_ln_rd_subsidy"] = (
        S_2017_2024["manufacturing_post2021"] * S_2017_2024["ln_rd_subsidy"]
    )
    res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                          ["manufacturing_post2021", "ln_rd_subsidy",
                           "manufacturing_post2021_x_ln_rd_subsidy"],
                          "M9c_Subsidy_Interaction")
save_result("mechanism", res)

# 2017-2024 versions
res, summary = run_fe(S_2017_2024, "rd_intensity", ["manufacturing_post2021"],
                      "M9d_RD_Intensity_2017_2024")
save_result("mechanism", res)

res, summary = run_fe(S_2017_2024, "ln_rd_staff", ["manufacturing_post2021"],
                      "M9e_RD_Staff_2017_2024")
save_result("mechanism", res)

res, summary = run_fe(S_2017_2024, "ln_invention_apply",
                      ["manufacturing_post2021", "ln_rd_subsidy",
                       "manufacturing_post2021_x_ln_rd_subsidy"],
                      "M9f_Subsidy_Interaction_2017_2024")
save_result("mechanism", res)

# ============================================================
# M10: 省级财政科技支出调节效应
# ============================================================
print("\n--- M10: 省级财政科技支出调节 ---")

# M10a: DID × 省级财政科技支出占比 (连续)
res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                      ["manufacturing_post2021", "did_x_prov_sci_tech"],
                      "M10a_DID_x_ProvSciTech",
                      extra_ctrl=["province_sci_tech_ratio"])
save_result("provincial", res)

# M10b: DID × 省级R&D强度
res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                      ["manufacturing_post2021", "did_x_prov_rd_intensity"],
                      "M10b_DID_x_ProvRD",
                      extra_ctrl=["province_rd_intensity"])
save_result("provincial", res)

# M10c: 分组 - 高/低财政科技支出省份
for hv, hl in [(1, "M10c_High_SciTech_Prov"), (0, "M10d_Low_SciTech_Prov")]:
    d_sub = S_2017_2022[S_2017_2022["high_sci_tech_province"] == hv].copy()
    if len(d_sub) > 100:
        res, summary = run_fe(d_sub, "ln_invention_apply", ["manufacturing_post2021"],
                              f"{hl}_2017_2022")
        save_result("provincial", res)

# M10e: 三重差分
res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                      ["manufacturing_post2021", "did_x_high_sci_prov",
                       "high_sci_tech_province"],
                      "M10e_Triple_Diff_HighSciProv")
save_result("provincial", res)

# M10f: DID × ln(省级财政科技支出)
res, summary = run_fe(S_2017_2022, "ln_invention_apply",
                      ["manufacturing_post2021", "did_x_ln_prov_sci"],
                      "M10f_DID_x_ln_ProvSci",
                      extra_ctrl=["ln_province_sci_tech_exp"])
save_result("provincial", res)

# 2017-2024
res, summary = run_fe(S_2017_2024, "ln_invention_apply",
                      ["manufacturing_post2021", "did_x_prov_sci_tech"],
                      "M10g_DID_x_ProvSciTech_2017_2024",
                      extra_ctrl=["province_sci_tech_ratio"])
save_result("provincial", res)

# ============================================================
# M11: 事件研究 (Event Study)
# ============================================================
print("\n--- M11: 事件研究 ---")

# 2017-2022 event study (baseline=2020)
es_df_2022 = S_2017_2022.copy()
es_df_2022["rel_year"] = es_df_2022["year"] - 2021
ev_vars_2022 = []
for k in range(-4, 2):  # -4 to 1, omit -1 (2020)
    if k == -1:
        continue
    year_val = 2021 + k
    name = f"event_{year_val}"
    es_df_2022[name] = ((es_df_2022["year"] == year_val).astype(float) * es_df_2022["manufacturing"]).astype(float)
    if es_df_2022[name].sum() > 0 and es_df_2022[name].std() > 0:
        ev_vars_2022.append(name)
print(f"  2017-2022 event vars: {ev_vars_2022}")

res, summary = run_fe(es_df_2022, "ln_invention_apply", ev_vars_2022,
                      "M11a_Event_Study_2017_2022")
save_result("event_study", res)
all_summaries.append(f"\n{'='*100}\nM11a: Event Study 2017-2022, baseline=2020\n{summary}")

# 2017-2024 event study (baseline=2020)
es_df_2024 = S_2017_2024.copy()
es_df_2024["rel_year"] = es_df_2024["year"] - 2021
ev_vars_2024 = []
for k in range(-4, 4):  # -4 to 3, omit -1 (2020)
    if k == -1:
        continue
    year_val = 2021 + k
    name = f"event_{year_val}"
    es_df_2024[name] = ((es_df_2024["year"] == year_val).astype(float) * es_df_2024["manufacturing"]).astype(float)
    if es_df_2024[name].sum() > 0 and es_df_2024[name].std() > 0:
        ev_vars_2024.append(name)
print(f"  2017-2024 event vars: {ev_vars_2024}")

res, summary = run_fe(es_df_2024, "ln_invention_apply", ev_vars_2024,
                      "M11b_Event_Study_2017_2024")
save_result("event_study", res)
all_summaries.append(f"\n{'='*100}\nM11b: Event Study 2017-2024, baseline=2020\n{summary}")

# ============================================================
# M12: 安慰剂检验 (Placebo)
# ============================================================
print("\n--- M12: 安慰剂检验 ---")

# Placebo 2019
res, summary = run_fe(S_2017_2020, "ln_invention_apply", ["manufacturing_post2019"],
                      "M12a_Placebo_2019")
save_result("placebo", res)

# Placebo 2020
res, summary = run_fe(S_2017_2020, "ln_invention_apply", ["manufacturing_post2020"],
                      "M12b_Placebo_2020")
save_result("placebo", res)

# ============================================================
# M13: PSM-DID (Propensity Score Matching)
# ============================================================
print("\n--- M13: PSM-DID ---")

# Step 1: Estimate propensity score using 2020 cross-section
df_2020 = S_2017_2022[S_2017_2022["year"] == 2020].copy()
psm_vars = ["ln_assets", "roa", "cashflow_ratio", "firm_age"]
psm_data = df_2020[["stock_code", "manufacturing"] + psm_vars].copy()
for v in psm_vars:
    psm_data[v] = pd.to_numeric(psm_data[v], errors="coerce")
psm_data = psm_data.dropna()

if len(psm_data) > 100 and psm_data["manufacturing"].nunique() >= 2:
    # Standardize
    scaler = StandardScaler()
    X = scaler.fit_transform(psm_data[psm_vars].fillna(0))
    y = psm_data["manufacturing"].values

    # Logistic regression for propensity score
    logit = LogisticRegression(max_iter=1000, random_state=42)
    logit.fit(X, y)
    psm_data["pscore"] = logit.predict_proba(X)[:, 1]

    # Trim common support
    p_min = max(psm_data[psm_data["manufacturing"] == 1]["pscore"].min(),
                psm_data[psm_data["manufacturing"] == 0]["pscore"].min())
    p_max = min(psm_data[psm_data["manufacturing"] == 1]["pscore"].max(),
                psm_data[psm_data["manufacturing"] == 0]["pscore"].max())
    psm_data["on_support"] = (psm_data["pscore"] >= p_min) & (psm_data["pscore"] <= p_max)

    psm_on = psm_data[psm_data["on_support"]]
    mfg_pscore = psm_on[psm_on["manufacturing"] == 1]["pscore"]
    nonmfg_pscore = psm_on[psm_on["manufacturing"] == 0]["pscore"]

    # Nearest neighbor matching
    matched_codes = set()
    for _, mfg_row in psm_on[psm_on["manufacturing"] == 1].iterrows():
        # Find closest non-manufacturing firm
        dist = (nonmfg_pscore - mfg_row["pscore"]).abs()
        if len(dist) > 0:
            best_idx = dist.idxmin()
            matched_codes.add(mfg_row["stock_code"])
            matched_codes.add(psm_on.loc[best_idx, "stock_code"])

    print(f"  PSM: {psm_on['manufacturing'].sum():,} treated, "
          f"{len(psm_on) - psm_on['manufacturing'].sum():,} control on support")
    print(f"  Matched firms: {len(matched_codes):,}")

    # Run DID on matched sample
    S_psm = S_2017_2022[S_2017_2022["stock_code"].isin(matched_codes)].copy()
    if len(S_psm) > 100:
        # Balance check
        balance_rows = []
        for v in psm_vars:
            mfg_mean = df_2020[df_2020["manufacturing"] == 1][v].mean()
            nonmfg_mean = df_2020[df_2020["manufacturing"] == 0][v].mean()
            mfg_std = df_2020[df_2020["manufacturing"] == 1][v].std()
            # SMD before matching
            smd_before = (mfg_mean - nonmfg_mean) / np.sqrt((mfg_std**2 + df_2020[df_2020["manufacturing"]==0][v].std()**2) / 2)

            ps_mfg = S_psm[S_psm["manufacturing"] == 1]
            ps_nonmfg = S_psm[S_psm["manufacturing"] == 0]
            ps_mfg_2020 = ps_mfg[ps_mfg["year"] == 2020]
            ps_nonmfg_2020 = ps_nonmfg[ps_nonmfg["year"] == 2020]
            if len(ps_mfg_2020) > 0 and len(ps_nonmfg_2020) > 0:
                smd_after = (ps_mfg_2020[v].mean() - ps_nonmfg_2020[v].mean()) / np.sqrt(
                    (ps_mfg_2020[v].std()**2 + ps_nonmfg_2020[v].std()**2) / 2)
            else:
                smd_after = np.nan
            balance_rows.append(dict(variable=v, smd_before=smd_before, smd_after=smd_after,
                                     mfg_mean_before=mfg_mean, nonmfg_mean_before=nonmfg_mean))

        balance_df = pd.DataFrame(balance_rows)
        save_result("psm", balance_df)
        print(f"  协变量平衡: SMD before={balance_df['smd_before'].abs().mean():.3f}, "
              f"SMD after={balance_df['smd_after'].abs().mean():.3f}")

        # PSM-DID regression
        res, summary = run_fe(S_psm, "ln_invention_apply", ["manufacturing_post2021"],
                              "M13a_PSM_DID")
        save_result("psm", res)

    # IPW weights
    S_2017_2022_w = S_2017_2022.copy()
    # Merge pscore
    pscore_map = psm_data.set_index("stock_code")["pscore"]
    S_2017_2022_w["pscore"] = S_2017_2022_w["stock_code"].map(pscore_map)
    S_2017_2022_w["ipw"] = np.where(
        S_2017_2022_w["manufacturing"] == 1,
        1 / S_2017_2022_w["pscore"],
        1 / (1 - S_2017_2022_w["pscore"])
    )
    S_2017_2022_w["ipw"] = S_2017_2022_w["ipw"].clip(lower=0.1, upper=10)

    # IPW-weighted DID — use linearmodels with weights if available
    d_ipw = S_2017_2022_w[["stock_code", "year", "ln_invention_apply",
                            "manufacturing_post2021", "ln_assets", "roa",
                            "cashflow_ratio", "firm_age", "ipw"]].copy()
    for c in ["ln_invention_apply", "manufacturing_post2021", "ln_assets", "roa",
              "cashflow_ratio", "firm_age"]:
        d_ipw[c] = pd.to_numeric(d_ipw[c], errors="coerce")
    d_ipw = d_ipw.dropna()

    if len(d_ipw) > 100 and HAS_LINEARMODELS:
        try:
            # Weighted PanelOLS
            pdata = d_ipw.set_index(["stock_code", "year"])
            formula = "ln_invention_apply ~ 1 + manufacturing_post2021 + ln_assets + roa + cashflow_ratio + firm_age + EntityEffects + TimeEffects"
            res_wls = PanelOLS.from_formula(formula, data=pdata, weights=d_ipw.set_index(["stock_code", "year"])["ipw"],
                                             drop_absorbed=True).fit(cov_type="clustered", cluster_entity=True)
            ipw_rows = []
            for v in ["manufacturing_post2021", "ln_assets", "roa", "cashflow_ratio", "firm_age"]:
                if v in res_wls.params.index:
                    ipw_rows.append(dict(model="M13b_IPW_DID", dependent="ln_invention_apply",
                        variable=v, coef=float(res_wls.params[v]),
                        std_err=float(res_wls.std_errors[v]), p_value=float(res_wls.pvalues[v]),
                        nobs=int(res_wls.nobs), firms=int(d_ipw["stock_code"].nunique()),
                        years=int(d_ipw["year"].nunique()), r2_within=float(res_wls.rsquared_within) if res_wls.rsquared_within else None,
                        engine="IPW-PanelOLS"))
            if ipw_rows:
                save_result("psm", pd.DataFrame(ipw_rows))
                print(f"  IPW-DID: N={int(res_wls.nobs):,}")
        except Exception as e:
            print(f"  IPW-DID FAILED: {str(e)[:100]}")

else:
    print("  PSM: insufficient data for propensity score estimation")

# ============================================================
# M14: 稳健性检验 - 删 2024
# ============================================================
print("\n--- M14: 稳健性 (drop 2024) ---")
S_2017_2023 = S_2017_2024[S_2017_2024["year"] != 2024].copy()
res, summary = run_fe(S_2017_2023, "ln_invention_apply", ["manufacturing_post2021"],
                      "M14a_Drop_2024")
save_result("robustness_alt_dv", res)

# ============================================================
# M15: 扩展样本 (2016-2022)
# ============================================================
print("\n--- M15: 扩展样本 (2016-2022) ---")
res, summary = run_fe(S_2016_2022, "ln_invention_apply", ["manufacturing_post2021"],
                      "M15a_2016_2022")
save_result("robustness_alt_dv", res)

# ============================================================
# M16: SOE 异质性
# ============================================================
print("\n--- M16: SOE 异质性 ---")
for soe_val, soe_label in [(1, "M16a_SOE"), (0, "M16b_NonSOE")]:
    d_sub = S_2017_2022[S_2017_2022["soe"] == soe_val].copy()
    if len(d_sub) > 100:
        res, summary = run_fe(d_sub, "ln_invention_apply", ["manufacturing_post2021"],
                              soe_label)
        save_result("heterogeneity_soe", res)

# ============================================================
# 4. 保存所有结果
# ============================================================
print("\n" + "=" * 80)
print("4. 保存结果")
print("=" * 80)

BUCKET_FILES = {
    "baseline": "final_baseline_results.csv",
    "robustness_alt_dv": "final_alt_outcome_results.csv",
    "ppml": "final_ppml_results.csv",
    "stage_policy": "final_stage_policy_results.csv",
    "policy_exposure": "final_policy_exposure_results.csv",
    "heterogeneity_pre_rd": "final_heterogeneity_results.csv",
    "heterogeneity_hightech": "final_heterogeneity_results.csv",
    "heterogeneity_soe": "final_heterogeneity_results.csv",
    "mechanism": "final_mechanism_results.csv",
    "provincial": "final_province_interaction_results.csv",
    "event_study": "final_event_study_results.csv",
    "placebo": "final_placebo_results.csv",
    "psm": "final_psm_ipw_results.csv",
}

# Combine heterogeneity sub-buckets
for bucket_name in ["heterogeneity_pre_rd", "heterogeneity_hightech", "heterogeneity_soe"]:
    if bucket_name in all_results:
        if "heterogeneity" not in all_results:
            all_results["heterogeneity"] = []
        all_results["heterogeneity"].extend(all_results[bucket_name])

# Write each bucket
for bucket, fname in BUCKET_FILES.items():
    tables = all_results.get(bucket, [])
    if tables:
        combined = pd.concat(tables, ignore_index=True)
        # Deduplicate
        combined = combined.drop_duplicates(
            subset=[c for c in ["model", "dependent", "variable"] if c in combined.columns],
            keep="first")
        combined.to_csv(OUT / fname, index=False, encoding="utf-8-sig")
        print(f"  {fname}: {len(combined)} rows")
    else:
        print(f"  {fname}: NO RESULTS (creating empty)")
        pd.DataFrame(columns=["model", "dependent", "variable", "coef", "std_err",
                              "p_value", "nobs", "firms", "years", "r2_within", "engine"]).to_csv(
            OUT / fname, index=False, encoding="utf-8-sig")

# Create a combined heterogeneity file
if "heterogeneity" in all_results:
    het_combined = pd.concat(all_results["heterogeneity"], ignore_index=True)
    het_combined = het_combined.drop_duplicates(
        subset=[c for c in ["model", "dependent", "variable"] if c in het_combined.columns],
        keep="first")
    het_combined.to_csv(OUT / "final_heterogeneity_results.csv", index=False, encoding="utf-8-sig")
    print(f"  final_heterogeneity_results.csv: {len(het_combined)} rows (combined)")

# Full model summaries
with open(OUT / "final_full_model_summaries.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_summaries))

# ============================================================
# 5. 数据审计报告
# ============================================================
print("\n" + "=" * 80)
print("5. 数据审计报告")
print("=" * 80)

audit_lines = []
audit_lines.append("# 最终数据审计报告\n")
audit_lines.append("## 面板唯一性确认\n")
audit_lines.append(f"- 全样本 (2016-2025): {len(df_all):,} obs × {df_all['stock_code'].nunique():,} firms")
audit_lines.append(f"- 全样本 stock_code-year 重复: **{dup_all}** (必须为 0)")
audit_lines.append("")
audit_lines.append("| 样本 | Obs | Firms | Dup | Max Obs/Firm | Mfg% |")
audit_lines.append("|------|-----|-------|-----|-------------|------|")
for label, s in samples.items():
    dup = s.duplicated(subset=["stock_code", "year"]).sum()
    max_obs = s.groupby("stock_code").size().max()
    yr_start, yr_end = [int(x) for x in label.split("(")[0].split("-")]
    audit_lines.append(f"| {label} | {len(s):,} | {s['stock_code'].nunique():,} | {dup} | {max_obs} | {s['manufacturing'].mean():.1%} |")
audit_lines.append("")
audit_lines.append("**最终面板为唯一企业年度面板，不存在 stock_code-year 重复观测。**\n")

audit_lines.append("## 关键变量覆盖率 (2017-2022)\n")
audit_lines.append("| 变量 | 缺失率 | 均值 | 标准差 | Min | Max |")
audit_lines.append("|------|--------|------|--------|-----|-----|")
for v in ["ln_invention_apply", "ln_invention_grant", "ln_patent_apply_total",
           "ln_patent_grant_total", "invention_apply", "invention_grant",
           "rd_intensity", "ln_rd_staff", "rd_staff_ratio", "ln_assets", "roa",
           "firm_age", "cashflow_ratio", "soe", "manufacturing", "manufacturing_post2021",
           "ln_rd_subsidy", "ln_total_subsidy", "policy_exposure", "pre_rd_intensity",
           "province_sci_tech_ratio", "province_rd_intensity"]:
    if v in S_2017_2022.columns:
        col = pd.to_numeric(S_2017_2022[v], errors="coerce")
        audit_lines.append(f"| {v} | {col.isna().mean():.1%} | {col.mean():.4g} | "
                           f"{col.std():.4g} | {col.min():.4g} | {col.max():.4g} |")
audit_lines.append("")

audit_lines.append("## 省级变量覆盖率 (2017-2022)\n")
audit_lines.append("| 变量 | 缺失率 | 均值 |")
audit_lines.append("|------|--------|------|")
for v in ["province_sci_tech_ratio", "province_rd_intensity", "province_sci_tech_exp",
           "province_rd_expenditure", "province_gdp"]:
    if v in S_2017_2022.columns:
        col = pd.to_numeric(S_2017_2022[v], errors="coerce")
        audit_lines.append(f"| {v} | {col.isna().mean():.1%} | {col.mean():.4g} |")
audit_lines.append("")

audit_lines.append("## 制造业与高技术制造业\n")
audit_lines.append(f"- 制造业占比 (2017-2022): {S_2017_2022['manufacturing'].mean():.1%}")
audit_lines.append(f"- 高技术制造业占比 (of all firms): {S_2017_2022['hightech_manufacturing'].mean():.1%}")
audit_lines.append(f"- 高技术制造业占比 (of manufacturing): {S_2017_2022[S_2017_2022['manufacturing']==1]['hightech_manufacturing'].mean():.1%}")
audit_lines.append(f"- 狭义高技术制造业占比 (of manufacturing): {S_2017_2022[S_2017_2022['manufacturing']==1]['hightech_narrow'].mean():.1%}")
audit_lines.append(f"- 高技术行业代码: {HIGHTECH_CODES}")
audit_lines.append("")

audit_lines.append("## 控制变量说明\n")
audit_lines.append("- `lev` (资产负债率): **不可得** — CSMAR 资产负债表仅含 A001000000 (资产总计), 使用 cashflow_ratio 作为补充控制变量")
audit_lines.append("- `firm_age`: 从 EstablishDate 计算, 可能因日期缺失而为 NaN")
audit_lines.append("- `soe`: 来自 HLD_Contrshr.S0702b, controller_type 以 '1' 开头为国有")
audit_lines.append("")

audit_lines.append("## 财务数据口径\n")
audit_lines.append("- 利润表/资产负债表/现金流量表: Typrep=A (合并报表), 仅 12月31日")
audit_lines.append("- 政府补助表: Typrep=1 (合并报表), 关键词匹配研发相关项目")
audit_lines.append("- 专利表: Area=1 (国内专利), 按 stock_code-year-ApplyType 聚合")
audit_lines.append("")

audit_lines.append("## 估算变量说明\n")
audit_lines.append("- `tax_saving_est`: RDSpendSum × rd_deduction_rate × 0.25 — **估算值, 非真实税务数据**")
audit_lines.append("- `policy_exposure`: pre_rd_intensity × manufacturing × post2021 — 外生暴露强度")
audit_lines.append("- `pre_rd_intensity`: 2017-2020 年企业平均 rd_intensity")

with open(OUT / "final_data_audit.md", "w", encoding="utf-8") as f:
    f.write("\n".join(audit_lines))

# Missing rates
s_vars = [c for c in S_2017_2022.columns if S_2017_2022[c].dtype in ['float64', 'int64', 'float32', 'Int64']]
miss = S_2017_2022[s_vars].isna().mean().sort_values(ascending=False)
miss.to_csv(OUT / "final_missing_rates.csv", encoding="utf-8-sig")

# Descriptive statistics
desc_vars = [c for c in ["ln_invention_apply", "ln_invention_grant", "ln_patent_apply_total",
    "ln_patent_grant_total", "invention_apply", "invention_grant", "patent_apply_total",
    "patent_grant_total", "rd_intensity", "ln_rd_staff", "rd_staff_ratio",
    "ln_assets", "roa", "firm_age", "cashflow_ratio", "ln_rd_subsidy",
    "ln_total_subsidy", "policy_exposure", "pre_rd_intensity",
    "province_sci_tech_ratio", "province_rd_intensity",
    "manufacturing", "soe", "hightech_manufacturing", "high_pre_rd"]
    if c in S_2017_2022.columns]
desc = S_2017_2022[desc_vars].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).T
desc.to_csv(OUT / "final_descriptive_statistics.csv", encoding="utf-8-sig")

# ============================================================
# 6. 模型比较总表
# ============================================================
print("\n" + "=" * 80)
print("6. 模型比较总表")
print("=" * 80)

# Gather all results into one big table
all_tables = []
for bucket in BUCKET_FILES:
    fpath = OUT / BUCKET_FILES[bucket]
    if fpath.exists():
        t = pd.read_csv(fpath)
        if len(t) > 0:
            all_tables.append(t)

if all_tables:
    model_table = pd.concat(all_tables, ignore_index=True)
    # Keep only key variables of interest
    key_patterns = [
        "manufacturing_post2021", "treat_2021_2022", "treat_2023_2024",
        "policy_exposure", "did_x_prov_sci_tech", "did_x_high_sci_prov",
        "did_x_prov_rd_intensity", "did_x_ln_prov_sci",
        "hightech_post2021", "hightech_narrow_post2021",
        "manufacturing_post2019", "manufacturing_post2020",
        "ln_rd_subsidy", "manufacturing_post2021_x_ln_rd_subsidy",
        "event_20", "JOINT_TEST", "WALD_STAGE",
    ]
    pattern = "|".join(key_patterns)
    key_rows = model_table[model_table["variable"].str.contains(pattern, na=False)]

    # Add conclusion type
    def classify_conclusion(row):
        p = row.get("p_value", None)
        coef = row.get("coef", None)
        var = str(row.get("variable", ""))
        mdl = str(row.get("model", ""))

        if pd.isna(p) or pd.isna(coef):
            return "模型未收敛"
        if p < 0.01:
            sig = "显著(1%)"
        elif p < 0.05:
            sig = "显著(5%)"
        elif p < 0.10:
            sig = "边际显著(10%)"
        else:
            sig = "不显著"

        if coef > 0:
            direction = "正向"
        else:
            direction = "负向"

        if "placebo" in mdl.lower() or "placebo" in var.lower():
            return f"安慰剂{sig}" if p >= 0.05 else f"安慰剂{sig}(警示)"
        if "event" in var.lower():
            return f"事件研究{sig}"
        if "joint" in var.lower():
            return "联合检验"

        return f"{direction}{sig}"

    model_table["conclusion_type"] = model_table.apply(classify_conclusion, axis=1)

    # Select display columns
    display_cols = ["model", "dependent", "variable", "coef", "std_err", "p_value",
                    "nobs", "firms", "conclusion_type", "engine"]
    display = model_table[display_cols].copy()
    display.to_csv(OUT / "final_model_comparison_table.csv", index=False, encoding="utf-8-sig")
    print(f"  final_model_comparison_table.csv: {len(display)} rows")

# ============================================================
# 7. 生成实证报告
# ============================================================
print("\n" + "=" * 80)
print("7. 生成实证报告")
print("=" * 80)

# Helper: find key coefficient
def find_coef(bucket_name, model_pattern, var_pattern):
    tables = all_results.get(bucket_name, [])
    if not tables:
        # Try reading from file
        fname = BUCKET_FILES.get(bucket_name)
        if fname:
            fpath = OUT / fname
            if fpath.exists():
                try:
                    t = pd.read_csv(fpath)
                    mask = (t["model"].str.contains(model_pattern, na=False)) & \
                           (t["variable"].str.contains(var_pattern, na=False))
                    if mask.any():
                        return t[mask].iloc[0]
                except Exception:
                    pass
        return None
    for t in tables:
        if "model" not in t.columns:
            continue
        mask = (t["model"].str.contains(model_pattern, na=False)) & \
               (t["variable"].str.contains(var_pattern, na=False))
        if mask.any():
            row = t[mask].iloc[0]
            return row
    return None

def format_result(row, prefix=""):
    if row is None:
        return f"{prefix}: 未估计"
    coef = row.get("coef")
    p = row.get("p_value")
    se = row.get("std_err")
    n = row.get("nobs")
    # Handle None or NaN
    if coef is None or (isinstance(coef, float) and np.isnan(coef)):
        return f"{prefix}: 模型未收敛或需外部工具(PPML)"
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return f"{prefix}: coef={coef:.4f}, se={se:.4f} (p值不可得), N={int(n) if n is not None and not np.isnan(n) else 'N/A'}"
    sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
    n_str = f"{int(n):,}" if n is not None and not (isinstance(n, float) and np.isnan(n)) else "N/A"
    return f"{prefix}: coef={coef:.4f}, se={se:.4f}, p={p:.4f}{sig}, N={n_str}"


rpt = []
rpt.append("# 科技自主创新政策实证研究 — 综合实证报告\n")
rpt.append(f"*生成时间: {time.strftime('%Y-%m-%d %H:%M')}*\n")

# 1. Data
rpt.append("## 1. 数据来源和样本说明\n")
rpt.append(f"- 数据来源: CSMAR (国泰安) 数据库, 8 张子表")
rpt.append(f"- 基准样本: 2017-2022, {len(S_2017_2022):,} obs × {S_2017_2022['stock_code'].nunique():,} firms")
rpt.append(f"- 制造业占比: {S_2017_2022['manufacturing'].mean():.1%}")
rpt.append(f"- 高技术制造业 (of manufacturing): {S_2017_2022[S_2017_2022['manufacturing']==1]['hightech_manufacturing'].mean():.1%}")
rpt.append(f"- 扩展样本: 2017-2024, {len(S_2017_2024):,} obs × {S_2017_2024['stock_code'].nunique():,} firms")
rpt.append(f"- 面板唯一性: **已确认, stock_code-year 无重复**")
rpt.append("")

# 2. Data structure audit
rpt.append("## 2. 数据结构审计\n")
rpt.append(f"- 全样本 stock_code-year 重复: **{dup_all}** ✓")
for label, s in samples.items():
    dup = s.duplicated(subset=["stock_code", "year"]).sum()
    max_obs = s.groupby("stock_code").size().max()
    yr_start, yr_end = [int(x) for x in label.split("(")[0].split("-")]
    rpt.append(f"- {label}: dup={dup}, max_obs/firm={max_obs} (expected ≤{yr_end-yr_start+1})")
rpt.append("")
rpt.append("**最终面板为唯一企业年度面板，不存在 stock_code-year 重复观测。**\n")

# 3. Variable definitions
rpt.append("## 3. 变量定义\n")
rpt.append("- `ln_invention_apply`: log(1 + 发明专利申请数)")
rpt.append("- `ln_invention_grant`: log(1 + 发明专利授权数)")
rpt.append("- `ln_patent_apply_total`: log(1 + 专利总申请数)")
rpt.append("- `ln_patent_grant_total`: log(1 + 专利总授权数)")
rpt.append("- `manufacturing`: 制造业=1 (行业代码C开头或名称含'制造')")
rpt.append("- `post2021`: year≥2021")
rpt.append("- `manufacturing_post2021`: manufacturing × post2021 (核心DID)")
rpt.append("- `treat_2021_2022`: manufacturing × 1[2021≤year≤2022]")
rpt.append("- `treat_2023_2024`: manufacturing × 1[year≥2023]")
rpt.append("- `policy_exposure`: pre_rd_intensity × manufacturing × post2021")
rpt.append("- `pre_rd_intensity`: 企业2017-2020年rd_intensity均值")
rpt.append("- 控制变量: ln_assets, roa, cashflow_ratio, firm_age")
rpt.append("- 固定效应: 企业FE + 年份FE, 聚类标准误按stock_code")
rpt.append("")

# 4. Policy background
rpt.append("## 4. 政策背景\n")
rpt.append("- 2021年: 制造业研发费用加计扣除比例从75%提高至100%")
rpt.append("- 2023年起: 全行业普遍适用100%加计扣除(普惠化)")
rpt.append("- 识别策略: 2017-2022为制造业vs非制造业政策差异的清洁识别窗口")
rpt.append("- 2023-2024: 对照组受政策污染, 仅用于阶段比较和趋势展示")
rpt.append("")

# 5. Baseline DID
rpt.append("## 5. 主DID模型\n")

# 2017-2022
row_m1 = find_coef("baseline", "M1_Baseline_DID_2017", "manufacturing_post2021")
rpt.append(f"### 5.1 基准模型 (2017-2022)\n")
rpt.append(format_result(row_m1, "manufacturing_post2021"))
rpt.append("")

if row_m1 is not None and row_m1.get("p_value", 1) > 0.10:
    rpt.append("**结论**: 制造业研发费用加计扣除政策(2021年提高至100%)的平均效应**不显著**。")
    rpt.append("在当前数据中, 制造业企业相对非制造业企业在2021年后未出现显著的发明专利申请增长。")
elif row_m1 is not None and row_m1.get("coef", 0) > 0:
    rpt.append("**结论**: 政策平均效应显著促进制造业企业创新。")
else:
    rpt.append("**结论**: manufacturing_post2021系数为负且显著, 需谨慎解释。")
rpt.append("")

# 5b: 2017-2024 with post2023
row_m1b = find_coef("baseline", "M1b", "manufacturing_post2021")
rpt.append(f"### 5.2 扩展模型 (2017-2024, 控制post2023)\n")
rpt.append(format_result(row_m1b, "manufacturing_post2021"))
rpt.append("注: 2023年起全行业100%加计扣除, post2023控制稀释效应。")
rpt.append("")

# 6. Alternative DVs
rpt.append("## 6. 替代因变量稳健性\n")
rpt.append("| 因变量 | 模型 | Coef | SE | p | N |")
rpt.append("|--------|------|------|-----|---|--|")
for dep, mdl_pat in [("ln_invention_grant", "M3a"), ("ln_patent_apply_total", "M3b"),
                      ("ln_patent_grant_total", "M3c")]:
    row = find_coef("robustness_alt_dv", mdl_pat, "manufacturing_post2021")
    if row is not None:
        sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.10 else ""
        rpt.append(f"| {dep} | {row['model']} | {row['coef']:.4f}{sig} | {row['std_err']:.4f} | {row['p_value']:.4f} | {int(row['nobs']):,} |")
rpt.append("")
rpt.append("**解释**: 若发明专利申请不显著但专利总申请显著, 说明政策可能更多影响数量型创新。")
rpt.append("若发明专利和授权均不显著, 则不能支持高质量创新促进结论。")
rpt.append("")

# 7. PPML
rpt.append("## 7. PPML计数模型\n")
for dep, mdl_pat in [("invention_apply", "M4a"), ("invention_grant", "M4b")]:
    row = find_coef("ppml", mdl_pat, "manufacturing_post2021")
    rpt.append(format_result(row, dep))
rpt.append("")

# 8. Stage policy
rpt.append("## 8. 政策阶段分析 (2017-2024)\n")
row_s1 = find_coef("stage_policy", "M5_Stage", "treat_2021_2022")
row_s2 = find_coef("stage_policy", "M5_Stage", "treat_2023_2024")
rpt.append(format_result(row_s1, "treat_2021_2022 (制造业优先激励阶段)"))
rpt.append(format_result(row_s2, "treat_2023_2024 (普惠化后制造业相对变化)"))

# Wald test
row_wald = find_coef("stage_policy", "M5_Stage", "WALD_STAGE")
if row_wald is not None:
    rpt.append(f"Wald检验 (β1=β2): stat={row_wald['coef']:.4f}, p={row_wald['p_value']:.4f}")
rpt.append("")

# 9. Policy exposure
rpt.append("## 9. 政策暴露强度分析\n")
row_exp = find_coef("policy_exposure", "M6a_Exposure_2017", "policy_exposure")
row_exp_mfg = find_coef("policy_exposure", "M6a_Exposure_2017", "manufacturing_post2021")
rpt.append(format_result(row_exp, "policy_exposure"))
rpt.append(format_result(row_exp_mfg, "manufacturing_post2021 (控制)"))
rpt.append("")
if row_exp is not None and row_exp.get("p_value", 1) < 0.05:
    rpt.append("**结论**: 政策效果在政策前研发基础较强的制造业企业中更明显。")
    rpt.append("政策平均效应不一定显著, 但效果集中在研发基础好的企业。")
rpt.append("")

# 10. High/Low pre-RD
rpt.append("## 10. 高低研发基础分组\n")
row_h = find_coef("heterogeneity", "M7a_High", "manufacturing_post2021")
row_l = find_coef("heterogeneity", "M7b_Low", "manufacturing_post2021")
rpt.append(format_result(row_h, "高研发基础组"))
rpt.append(format_result(row_l, "低研发基础组"))
rpt.append("")

# 11. High-tech manufacturing
rpt.append("## 11. 高技术制造业异质性\n")
row_ht = find_coef("heterogeneity", "M8a_Hightech_x_Post", "hightech_post2021")
row_htn = find_coef("heterogeneity", "M8b_HightechNarrow", "hightech_narrow_post2021")
row_htm = find_coef("heterogeneity", "M8c_MFG_Only", "hightech_post2021")
rpt.append(format_result(row_ht, "高技术制造业×post2021 (全样本)"))
rpt.append(format_result(row_htn, "狭义高技术制造业×post2021"))
rpt.append(format_result(row_htm, "高技术制造业 (仅制造业样本)"))
rpt.append("")

# 12. Mechanism
rpt.append("## 12. 机制检验\n")
row_rd = find_coef("mechanism", "M9a_RD_Intensity", "manufacturing_post2021")
row_staff = find_coef("mechanism", "M9b_RD_Staff", "manufacturing_post2021")
row_sub = find_coef("mechanism", "M9c_Subsidy", "manufacturing_post2021_x")
rpt.append("### 12.1 研发投入强度机制\n")
rpt.append(format_result(row_rd, "rd_intensity"))
rpt.append("### 12.2 研发人员机制\n")
rpt.append(format_result(row_staff, "ln_rd_staff"))
rpt.append("### 12.3 研发补助协同\n")
if row_sub is not None:
    rpt.append(format_result(row_sub, "manufacturing_post2021 × ln_rd_subsidy"))
else:
    rpt.append("交互项未估计或模型未收敛")
rpt.append("")

# 13. Provincial
rpt.append("## 13. 省级财政科技支出调节效应\n")
row_p1 = find_coef("provincial", "M10a_DID_x_ProvSci", "did_x_prov_sci_tech")
row_p2 = find_coef("provincial", "M10b_DID_x_ProvRD", "did_x_prov_rd_intensity")
row_p3 = find_coef("provincial", "M10e_Triple", "did_x_high_sci_prov")
rpt.append(format_result(row_p1, "DID × 省财政科技支出占比"))
rpt.append(format_result(row_p2, "DID × 省R&D强度"))
rpt.append(format_result(row_p3, "DID × 高财政科技支出省 (三重差分)"))
rpt.append("")

# 14. Event study
rpt.append("## 14. 事件研究\n")
rpt.append("基准年: 2020 (政策前一年)\n")
rpt.append("| Year | Coef | SE | p |")
rpt.append("|------|------|-----|---|")
for yr in [2017, 2018, 2019, 2021, 2022]:
    row_ev = find_coef("event_study", "M11a", f"event_{yr}")
    if row_ev is not None:
        sig = "***" if row_ev["p_value"] < 0.01 else "**" if row_ev["p_value"] < 0.05 else "*" if row_ev["p_value"] < 0.10 else ""
        rpt.append(f"| {yr} | {row_ev['coef']:.4f}{sig} | {row_ev['std_err']:.4f} | {row_ev['p_value']:.4f} |")

row_joint_pre = find_coef("event_study", "M11a", "JOINT_TEST_PRE")
if row_joint_pre is not None:
    rpt.append(f"\n政策前趋势联合检验 (2017-2019): stat={row_joint_pre['coef']:.4f}, p={row_joint_pre['p_value']:.4f}")
rpt.append("")

# 15. Placebo
rpt.append("## 15. 安慰剂检验\n")
row_pl1 = find_coef("placebo", "M12a_Placebo_2019", "manufacturing_post2019")
row_pl2 = find_coef("placebo", "M12b_Placebo_2020", "manufacturing_post2020")
rpt.append(format_result(row_pl1, "Placebo 2019 (假政策=2019)"))
rpt.append(format_result(row_pl2, "Placebo 2020 (假政策=2020)"))
rpt.append("")

# 16. PSM/IPW
rpt.append("## 16. PSM/IPW 稳健性\n")
row_psm = find_coef("psm", "M13a_PSM", "manufacturing_post2021")
row_ipw = find_coef("psm", "M13b_IPW", "manufacturing_post2021")
rpt.append(format_result(row_psm, "PSM-DID"))
rpt.append(format_result(row_ipw, "IPW-DID"))
rpt.append("")

# 17. Model comparison summary
rpt.append("## 17. 结果总表\n")
rpt.append("完整模型比较见: `outputs/final/final_model_comparison_table.csv`\n")

# Gather key results
rpt.append("### 关键结果摘要\n")
rpt.append("| 模型 | 核心变量 | Coef | SE | p | 结论 |")
rpt.append("|------|----------|------|-----|---|------|")

key_models = [
    ("baseline", "M1_Baseline_DID_2017", "manufacturing_post2021", "主DID (2017-2022)"),
    ("robustness_alt_dv", "M3a", "manufacturing_post2021", "替代DV: 发明授权"),
    ("robustness_alt_dv", "M3b", "manufacturing_post2021", "替代DV: 专利总申请"),
    ("robustness_alt_dv", "M3c", "manufacturing_post2021", "替代DV: 专利总授权"),
    ("ppml", "M4a", "manufacturing_post2021", "PPML: 发明申请"),
    ("ppml", "M4b", "manufacturing_post2021", "PPML: 发明授权"),
    ("stage_policy", "M5_Stage", "treat_2021_2022", "阶段: 2021-2022"),
    ("stage_policy", "M5_Stage", "treat_2023_2024", "阶段: 2023-2024"),
    ("policy_exposure", "M6a", "policy_exposure", "政策暴露强度"),
    ("heterogeneity", "M7a_High", "manufacturing_post2021", "高研发基础组"),
    ("heterogeneity", "M7b_Low", "manufacturing_post2021", "低研发基础组"),
    ("heterogeneity", "M8a", "hightech_post2021", "高技术制造异质性"),
    ("mechanism", "M9a", "manufacturing_post2021", "机制: 研发强度"),
    ("mechanism", "M9b", "manufacturing_post2021", "机制: 研发人员"),
    ("mechanism", "M9c", "manufacturing_post2021_x", "机制: 补贴协同"),
    ("provincial", "M10a", "did_x_prov_sci_tech", "省级财政交互"),
    ("placebo", "M12a", "manufacturing_post2019", "安慰剂 2019"),
    ("placebo", "M12b", "manufacturing_post2020", "安慰剂 2020"),
    ("psm", "M13a", "manufacturing_post2021", "PSM-DID"),
]

def safe_p(p_val):
    """Safe p-value handling"""
    if p_val is None or (isinstance(p_val, float) and np.isnan(p_val)):
        return 1.0  # treat as not significant
    return p_val

def safe_sig(p_val):
    """Safe significance stars"""
    p = safe_p(p_val)
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""

def safe_fmt(val, fmt=".4f"):
    """Safe formatting"""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:{fmt}}"

for bucket, model_pat, var_pat, label in key_models:
    row = find_coef(bucket, model_pat, var_pat)
    if row is not None:
        pv = row.get("p_value")
        sig = safe_sig(pv)
        conclusion = classify_conclusion(row)
        coef_str = safe_fmt(row.get("coef"))
        se_str = safe_fmt(row.get("std_err"))
        p_str = safe_fmt(pv)
        var_str = str(row.get("variable", ""))
        rpt.append(f"| {label} | {var_str} | {coef_str}{sig} | {se_str} | {p_str} | {conclusion} |")
    else:
        rpt.append(f"| {label} | - | - | - | - | 未估计 |")
rpt.append("")

# 18. Conclusions
rpt.append("## 18. 有价值结论总结\n")

# Derive conclusions from results
conclusions = []

# Check baseline
if row_m1 is not None:
    p_m1 = safe_p(row_m1.get("p_value"))
    coef_m1 = row_m1.get("coef", 0) or 0
    if p_m1 < 0.05 and coef_m1 > 0:
        conclusions.append("1. **平均政策效应显著促进创新**: 2021年制造业研发费用加计扣除比例提高显著促进制造业企业发明专利申请。")
    elif p_m1 < 0.05 and coef_m1 < 0:
        conclusions.append("1. **平均政策效应为负**: manufacturing_post2021系数显著为负，需谨慎解释。可能反映制造业相对非制造业的创新表现下降，需结合行业周期、对照组变化等因素解释。")
    else:
        conclusions.append("1. **平均政策效应不显著**: 2021年制造业研发费用加计扣除政策的平均效应在当前数据中未显著促进制造业企业发明专利申请。")

# Check policy exposure
if row_exp is not None:
    p_exp = row_exp.get("p_value", 1)
    if p_exp < 0.05 and row_exp.get("coef", 0) > 0:
        conclusions.append("2. **政策效果集中在研发基础强的企业**: policy_exposure显著为正，说明政策前研发强度高的制造业企业在政策后获得更明显的创新提升。")
    elif p_exp < 0.05:
        conclusions.append("2. **政策暴露效应显著但方向异常**: policy_exposure系数显著但为负，需进一步检视。")
    else:
        conclusions.append("2. **政策暴露效应不显著**: 政策效果不集中在研发基础强的企业中。")

# Check high/low pre-RD
if row_h is not None and row_l is not None:
    p_h = row_h.get("p_value", 1)
    p_l = row_l.get("p_value", 1)
    if p_h < 0.10 and p_l >= 0.10:
        conclusions.append("3. **高研发基础组效果更强**: 政策效果主要集中在政策前研发能力较强的企业中，低研发基础组不显著。")
    elif p_h >= 0.10 and p_l >= 0.10:
        conclusions.append("3. **高低研发基础组均不显著**: 分组DID均不显著，政策效应无明显的研发基础异质性。")

# Check stage
if row_s1 is not None and row_s2 is not None:
    p_s1 = row_s1.get("p_value", 1)
    p_s2 = row_s2.get("p_value", 1)
    if p_s1 < 0.10 and p_s2 >= 0.10:
        conclusions.append("4. **政策普惠化后制造业相对优势减弱**: 2021-2022阶段制造业政策效果可见，但2023年普惠化后制造业相对非制造业的优势不再显著。")
    elif p_s1 >= 0.10 and p_s2 >= 0.10:
        conclusions.append("4. **两阶段均未发现显著制造业相对优势**: 无论是在2021-2022制造业优先激励期还是2023年后普惠化期，均未发现制造业相对非制造业的创新显著提升。")

# Check provincial
if row_p1 is not None:
    p_p1 = row_p1.get("p_value", 1)
    if p_p1 < 0.10:
        conclusions.append("5. **地方财政科技支出具有调节效应**: DID×省财政科技支出占比显著，说明地方财政科技投入强化了加计扣除政策的创新效应。")
    else:
        conclusions.append("5. **未发现地方财政科技支出显著调节政策效果**: 各省级财政交互项均不显著。")

# Check mechanism
if row_rd is not None and row_staff is not None:
    p_rd = row_rd.get("p_value", 1)
    p_staff = row_staff.get("p_value", 1)
    if p_rd < 0.10 and p_staff < 0.10:
        if row_rd.get("coef", 0) > 0:
            conclusions.append("6. **研发投入和人员机制成立**: 政策显著提升了制造业企业的研发投入强度和研发人员投入。")
        else:
            conclusions.append("6. **研发投入和人员机制不支持正向渠道**: 制造业企业相对非制造业在研发投入和人员方面未显著增长。")
    elif p_rd >= 0.10 and p_staff >= 0.10:
        conclusions.append("6. **机制检验未获得支持**: 研发投入强度和研发人员投入均不显著。")

# Overall
conclusions.append("")
conclusions.append("## 19. 局限性\n")
conclusions.append("- `lev` (资产负债率) 不可得, 控制变量可能不完全")
conclusions.append("- PPML 模型基于 GLM + dummies, 未使用 fixest/ppmlhdfe 专用算法, 标准误可能不准确")
conclusions.append("- 人均专利等变量未构造, 可能对异质性分析造成遗漏")
conclusions.append("- 行业代码粒度可能不足以完整识别高技术制造业")
conclusions.append("- `tax_saving_est` 为估算值, 非真实税务申报数据")
conclusions.append("- 2023年后对照组受政策污染, 2023-2024的估计不是清洁DID")
conclusions.append("- 事件研究的平行趋势检验为统计证据, 不能完全证明因果识别成立")
conclusions.append("- PSM-DID 的匹配质量依赖第一阶段倾向得分模型的正确设定")

for c in conclusions:
    rpt.append(c)

with open(OUT / "final_empirical_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(rpt))

# ============================================================
# 8. Print key results
# ============================================================
print("\n" + "=" * 80)
print("8. 关键结果")
print("=" * 80)

for label in ["主DID (2017-2022)", "Policy Exposure", "High Pre-RD", "Low Pre-RD",
              "Stage 2021-2022", "Stage 2023-2024", "Placebo 2019", "Placebo 2020"]:
    for bucket, model_pat, var_pat in [
        ("baseline", "M1_Baseline_DID_2017", "manufacturing_post2021"),
        ("policy_exposure", "M6a", "policy_exposure"),
        ("heterogeneity", "M7a_High", "manufacturing_post2021"),
        ("heterogeneity", "M7b_Low", "manufacturing_post2021"),
        ("stage_policy", "M5_Stage", "treat_2021_2022"),
        ("stage_policy", "M5_Stage", "treat_2023_2024"),
        ("placebo", "M12a", "manufacturing_post2019"),
        ("placebo", "M12b", "manufacturing_post2020"),
    ]:
        row = find_coef(bucket, model_pat, var_pat)
        if row is not None:
            sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.10 else ""
            print(f"  {label:25s}: coef={row['coef']:.4f}, se={row['std_err']:.4f}, p={row['p_value']:.4f}{sig}, N={int(row['nobs']):,}")

elapsed = time.time() - T0
print(f"\n总运行时间: {elapsed:.1f}s ({elapsed/60:.1f}min)")
print(f"\n所有输出: {OUT}/")
for f in sorted(os.listdir(OUT)):
    sz = os.path.getsize(OUT / f)
    print(f"  {f} ({sz:,} bytes)")

print("\nDONE: 综合模型分析全部完成")
