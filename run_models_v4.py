"""
科技自主创新政策实证研究 — v4 模型（含省级财政交互）
====================================================
v4 扩展:
  1. 基准样本扩展至 2017-2024
  2. 新增省级财政科技支出 × DID 交互分析
  3. 保留 v3 全部模型体系

输入: data/firm_panel_v4.csv
输出: outputs/v4/
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

try:
    from linearmodels.panel import PoissonRE
    HAS_POISSONRE = True
except Exception:
    HAS_POISSONRE = False

import time

OUT = Path("outputs/v4")
OUT.mkdir(parents=True, exist_ok=True)

# GPU 检测 (信息性: linearmodels 不支持 GPU 加速, 使用高效 CPU 吸收算法)
try:
    import subprocess
    gpu_info = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=5)
    if gpu_info.returncode == 0:
        print(f"  GPU: {gpu_info.stdout.strip()}")
        print(f"  注意: linearmodels 使用 CPU 吸收算法 (within-transformation), 无需 GPU.")
    else:
        print("  GPU: 无 NVIDIA GPU")
except Exception:
    print("  GPU: 无法检测")

T0 = time.time()

# ============================================================
# 1. 读取和准备
# ============================================================
print("=" * 80)
print("1. 读取数据")
print("=" * 80)

df_all = pd.read_csv("data/firm_panel_v4.csv")
df_all["stock_code"] = df_all["stock_code"].astype(str).str.zfill(6)
df_all["year"] = df_all["year"].astype(int)
print(f"  全量: {len(df_all):,} rows, dup={df_all.duplicated(subset=['stock_code','year']).sum()}")


def get_sample(df, start, end, name):
    d = df[df["year"].between(start, end)].copy()
    print(f"  {name}: {len(d):,} × {d['stock_code'].nunique():,} firms, "
          f"dup={d.duplicated(subset=['stock_code','year']).sum()}, "
          f"mfg={d['manufacturing'].mean():.1%}")
    return d


S_2017_2022 = get_sample(df_all, 2017, 2022, "2017-2022 (v3基准)")
S_2017_2024 = get_sample(df_all, 2017, 2024, "2017-2024 (v4扩展)")
S_2017_2020 = get_sample(df_all, 2017, 2020, "2017-2020 (安慰剂)")
S_2016_2022 = get_sample(df_all, 2016, 2022, "2016-2022")

# ============================================================
# 2. 回归引擎
# ============================================================
print("\n" + "=" * 80)
print("2. 回归引擎")
print("=" * 80)


def run_fe(df_in, y, xvars, name, extra_ctrl=None):
    """
    双向固定效应: entity + year FE, clustered by entity.
    仅使用 linearmodels.PanelOLS (高效吸收FE).
    firm_age 不包含在默认控制变量中 (与 time FE 共线, 被吸收).
    """
    ctrls_base = ["ln_assets", "roa", "cashflow_ratio"]
    ctrls = [c for c in ctrls_base if c in df_in.columns]
    if extra_ctrl:
        ctrls.extend([c for c in extra_ctrl if c in df_in.columns and c not in ctrls])

    all_x = xvars + ctrls
    needed = ["stock_code", "year", y] + all_x
    if not set(needed).issubset(df_in.columns):
        return None, f"MISSING: {[c for c in needed if c not in df_in.columns]}"

    d = df_in[needed].copy()
    for c in [y] + all_x:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna()
    if d.empty or d["stock_code"].nunique() < 10:
        return None, "NO_DATA"

    valid_x = [v for v in all_x if d[v].std() > 0 and d[v].nunique() > 1]
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
                rows.append(dict(model=name, dependent=y, variable=v,
                    coef=float(res.params[v]), std_err=float(res.std_errors[v]),
                    p_value=float(res.pvalues[v]), nobs=int(res.nobs),
                    firms=int(d["stock_code"].nunique()), years=int(d["year"].nunique()),
                    r2_within=float(res.rsquared_within) if res.rsquared_within else None,
                    engine="PanelOLS"))

        # Joint test for event study (Wald F-test on all event vars)
        if "event_" in " ".join(xvars):
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

        summary = str(res.summary)
        return pd.DataFrame(rows), summary
    except Exception as e:
        return None, f"PanelOLS_FAILED: {str(e)[:200]}"


def run_all(df, label, baseline_sample=False, run_provincial=True):
    """运行全部模型"""
    results: Dict[str, List] = {}
    summaries = []

    def add(bucket, result, title):
        if result is None:
            return
        tab, s = result
        if tab is not None and len(tab):
            if bucket not in results:
                results[bucket] = []
            results[bucket].append(tab)
            summaries.append(f"\n{'='*100}\n[{label}] {title}\n{s}")

    # ---- 基准 DID (2017-2024) ----
    add("baseline",
        run_fe(df, "ln_invention_apply", ["manufacturing_post2021"], "M1_Baseline_DID"),
        "M1: ln_invention_apply ~ manufacturing_post2021 + controls + FE")

    # ---- 基准 DID + post2023 控制 ----
    add("baseline",
        run_fe(df, "ln_invention_apply", ["manufacturing_post2021", "post2023"], "M1b_DID_ctrl_post2023"),
        "M1b: 基准 + post2023 控制 (2023+ 全行业100%加计扣除)")

    # ============================================================
    # 省级财政科技支出交互 (v4 核心新增)
    # ============================================================
    if run_provincial:
        # 交互项: DID × 省级财政科技支出占比 (连续)
        add("provincial_fiscal",
            run_fe(df, "ln_invention_apply",
                   ["manufacturing_post2021", "did_x_prov_sci_tech"],
                   "P1_prov_sci_tech_interact",
                   extra_ctrl=["province_sci_tech_ratio"]),
            "P1: DID + DID×省财政科技支出占比 + 省财政占比 (连续交互)")

        # 交互项: DID × 省R&D经费强度
        add("provincial_fiscal",
            run_fe(df, "ln_invention_apply",
                   ["manufacturing_post2021", "did_x_prov_rd_intensity"],
                   "P2_prov_rd_intensity_interact",
                   extra_ctrl=["province_rd_intensity"]),
            "P2: DID + DID×省R&D强度 + 省R&D强度 (连续交互)")

        # 交互项: DID × ln(省级财政科技支出)
        add("provincial_fiscal",
            run_fe(df, "ln_invention_apply",
                   ["manufacturing_post2021", "did_x_ln_prov_sci"],
                   "P3_prov_sci_exp_interact",
                   extra_ctrl=["ln_province_sci_tech_exp"]),
            "P3: DID + DID×ln(省财政科技支出) + ln(省财政科技支出)")

        # 三重差分: DID × 高财政科技支出省份
        add("provincial_fiscal",
            run_fe(df, "ln_invention_apply",
                   ["manufacturing_post2021", "did_x_high_sci_prov", "high_sci_tech_province"],
                   "P4_triple_diff_high_sci_prov"),
            "P4: 三重差分 — DID + DID×高财政科技省份 + 高财政省份")

        # 分样本: 高财政科技支出省份
        if "high_sci_tech_province" in df.columns and df["high_sci_tech_province"].sum() > 100:
            for hv, hl in [(1, "High_sci_tech_prov"), (0, "Low_sci_tech_prov")]:
                d_sub = df[df["high_sci_tech_province"] == hv].copy()
                if len(d_sub) > 100:
                    add("provincial_fiscal",
                        run_fe(d_sub, "ln_invention_apply", ["manufacturing_post2021"],
                               f"P5_{hl}_subsample"),
                        f"P5: {hl} 分样本 DID")

    # ---- 机制 ----
    add("mechanism",
        run_fe(df, "rd_intensity", ["manufacturing_post2021"], "M2a_RD_intensity"),
        "M2a: rd_intensity ~ manufacturing_post2021 (机制: 研发投入)")

    add("mechanism",
        run_fe(df, "ln_rd_staff", ["manufacturing_post2021"], "M2b_RD_staff"),
        "M2b: ln(1+rd_staff) ~ manufacturing_post2021 (机制: 人力投入)")

    add("mechanism",
        run_fe(df, "ln_invention_apply", ["manufacturing_post2021"], "M2c_subsidy_channel",
               extra_ctrl=["ln_rd_subsidy"]),
        "M2c: 基准 + ln(1+rd_subsidy) (机制: 补贴协同)")

    # ---- 政策暴露强度 ----
    add("mechanism",
        run_fe(df, "ln_invention_apply", ["manufacturing_post2021", "policy_exposure"],
               "M2d_policy_exposure"),
        "M2d: 基准 + policy_exposure (外生暴露强度)")

    # ---- 替代因变量 ----
    for dep, mdl in [
        ("ln_invention_grant", "M3a_grant"),
        ("ln_patent_apply_total", "M3b_patent_apply"),
        ("ln_patent_grant_total", "M3c_patent_grant"),
    ]:
        add("robustness",
            run_fe(df, dep, ["manufacturing_post2021"], mdl),
            f"{mdl}: {dep} ~ manufacturing_post2021")

    # ---- 安慰剂 (2017-2020) ----
    if baseline_sample:
        df_placebo = S_2017_2020.copy()
        if "manufacturing_post2019" not in df_placebo.columns:
            df_placebo["manufacturing_post2019"] = df_placebo["manufacturing"] * df_placebo["post2019"]
            df_placebo["manufacturing_post2020"] = df_placebo["manufacturing"] * df_placebo["post2020"]

        add("placebo",
            run_fe(df_placebo, "ln_invention_apply", ["manufacturing_post2019"], "M4a_placebo_2019"),
            "M4a (安慰剂): 2017-2020, 假政策=2019")

        add("placebo",
            run_fe(df_placebo, "ln_invention_apply", ["manufacturing_post2020"], "M4b_placebo_2020"),
            "M4b (安慰剂): 2017-2020, 假政策=2020")

    # ---- 事件研究 (2017-2024, baseline=2020) ----
    if baseline_sample:
        df_es = df.copy()
        df_es["rel_year"] = df_es["year"] - 2021
        ev_vars = []
        for k in range(-4, 4):  # 2017-2024: rel_year = -4 to 3, omit -1 (2020)
            if k == -1:
                continue
            name = f"event_m{abs(k)}" if k < 0 else f"event_p{k}"
            df_es[name] = ((df_es["rel_year"] == k).astype(float) * df_es["manufacturing"]).astype(float)
            if df_es[name].sum() > 0 and df_es[name].std() > 0:
                ev_vars.append(name)

        add("event_study",
            run_fe(df_es, "ln_invention_apply", ev_vars, "M5_event_study"),
            f"M5: Event study 2017-2024, baseline=2020, vars={ev_vars}")

    # ---- PPML ----
    # PPML 需要 Poisson pseudo-maximum-likelihood.
    # linearmodels 不提供 Poisson panel estimator; statsmodels GLM + dummies 内存爆炸.
    # v4 跳过 PPML, 线下可用 Stata (ppmlhdfe) 或 R (fixest::fepois) 补充.
    print("  [PPML] 跳过 — 线上不可用 (需 Stata ppmlhdfe 或 R fixest::fepois)")

    return results, summaries


# ============================================================
# 3. 运行所有样本
# ============================================================
print("\n" + "=" * 80)
print("3. 运行模型")
print("=" * 80)

all_res = {}
all_sums = []

for sample_df, label, is_base, run_prov in [
    (S_2017_2024, "2017_2024", True, True),
    (S_2017_2022, "2017_2022", True, True),
    (S_2016_2022, "2016_2022", False, False),
]:
    print(f"\n  --- {label} ---")
    r, s = run_all(sample_df, label, baseline_sample=is_base, run_provincial=run_prov)
    for k, v in r.items():
        if k not in all_res:
            all_res[k] = []
        all_res[k].extend(v)
    all_sums.extend(s)

# Drop 2024 from 2017-2024 for robustness
df_no2024 = S_2017_2024[S_2017_2024["year"] != 2024].copy()
r3 = run_fe(df_no2024, "ln_invention_apply", ["manufacturing_post2021"], "ROB_drop2024")
if r3 is not None:
    tab3, s3 = r3
    if tab3 is not None and len(tab3):
        if "robustness" not in all_res:
            all_res["robustness"] = []
        all_res["robustness"].append(tab3)
        all_sums.append(f"\n{'='*100}\n[drop2024] ROB: drop 2024\n{s3}")

# ============================================================
# 4. 保存结果
# ============================================================
print("\n" + "=" * 80)
print("4. 保存结果")
print("=" * 80)

BUCKETS = {
    "baseline": "v4_baseline_results.csv",
    "mechanism": "v4_mechanism_results.csv",
    "robustness": "v4_robustness_results.csv",
    "placebo": "v4_placebo_results.csv",
    "event_study": "v4_event_study.csv",
    "ppml": "v4_ppml_results.csv",
    "provincial_fiscal": "v4_provincial_fiscal_results.csv",
}

for bucket, fname in BUCKETS.items():
    tables = all_res.get(bucket, [])
    if tables:
        combined = pd.concat(tables, ignore_index=True)
        combined.to_csv(OUT / fname, index=False, encoding="utf-8-sig")
        print(f"  {fname}: {len(combined)} rows")
    else:
        print(f"  {fname}: NO RESULTS (empty)")

with open(OUT / "v4_full_model_summaries.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_sums))

# ============================================================
# 5. 数据审计
# ============================================================
print("\n" + "=" * 80)
print("5. 数据审计")
print("=" * 80)

audit_lines = []
audit_lines.append("# v4 数据审计报告\n")
audit_lines.append(f"## 面板概况\n")
audit_lines.append(f"- 全量: {len(df_all):,} obs × {df_all['stock_code'].nunique():,} firms")
audit_lines.append(f"- v4 扩展样本 (2017-2024): {len(S_2017_2024):,} obs × {S_2017_2024['stock_code'].nunique():,} firms")
audit_lines.append(f"- v3 基准样本 (2017-2022): {len(S_2017_2022):,} obs × {S_2017_2022['stock_code'].nunique():,} firms")
audit_lines.append(f"- 制造业占比 (2017-2024): {S_2017_2024['manufacturing'].mean():.1%}")
audit_lines.append(f"- SOE 覆盖率: {S_2017_2024['soe'].notna().mean():.1%}")
audit_lines.append(f"- 省份覆盖率: {S_2017_2024['province_clean'].notna().mean():.1%}")
audit_lines.append("")

audit_lines.append("## 省级变量覆盖率 (2017-2024)\n")
audit_lines.append("| 变量 | 缺失率 | 均值 | 标准差 |")
audit_lines.append("|------|--------|------|--------|")
s = S_2017_2024
for v in ["province_gdp", "province_sci_tech_exp", "province_sci_tech_ratio",
           "province_rd_expenditure", "province_rd_intensity",
           "did_x_prov_sci_tech", "did_x_high_sci_prov", "did_x_prov_rd_intensity"]:
    if v in s.columns:
        col = pd.to_numeric(s[v], errors="coerce")
        audit_lines.append(f"| {v} | {col.isna().mean():.1%} | {col.mean():.3g} | {col.std():.3g} |")
audit_lines.append("")

audit_lines.append("## 2024 年数据说明\n")
audit_lines.append("- `province_sci_tech_exp` (财政科技支出): 2024年全省份缺失，使用2023年值填充（假设年度间高稳定）")
audit_lines.append("- `province_rd_expenditure`: 2024年31/31覆盖（来源：2025年统计公报）")
audit_lines.append("- `province_rd_intensity`: 2024年31/31覆盖")
audit_lines.append("- 2023年 `province_rd_expenditure`: 仅12/31省份有数据（公报中部分省份未单独列出）")
audit_lines.append("")

audit_lines.append("## 省级财政交互模型说明\n")
audit_lines.append("- P1: DID + DID×省财政科技支出占比 — 检验地方财政科技投入如何调节加计扣除政策的创新效应")
audit_lines.append("- P2: DID + DID×省R&D强度 — 检验地区创新基础对政策效应的调节")
audit_lines.append("- P3: DID + DID×ln(省财政科技支出) — 用绝对规模替代占比")
audit_lines.append("- P4: 三重差分 — 高 vs 低财政科技支出省份的DID效应差异")
audit_lines.append("- P5: 分样本 — 高/低财政科技支出省份分别估计DID")
audit_lines.append("")

audit_lines.append("## 结论约束\n")
audit_lines.append("- `tax_saving_est` 是估算值，非真实税务数据")
audit_lines.append("- `province_sci_tech_exp` 2024年为2023年填充值，解释时需注明")
audit_lines.append("- PPML 模型可能存在收敛问题")
audit_lines.append("- 2023+ 全行业100%加计扣除稀释制造业_post2021处理效应")

with open(OUT / "v4_data_audit.md", "w", encoding="utf-8") as f:
    f.write("\n".join(audit_lines))

# 缺失率
s_vars = [c for c in S_2017_2024.columns if S_2017_2024[c].dtype in ['float64', 'int64', 'float32']]
miss = S_2017_2024[s_vars].isna().mean().sort_values(ascending=False)
miss.to_csv(OUT / "v4_missing_rates.csv", encoding="utf-8-sig")

# 描述性统计
desc_vars = [c for c in ["ln_invention_apply", "ln_invention_grant", "ln_patent_apply_total",
    "ln_patent_grant_total", "rd_intensity", "ln_rd_staff", "rd_staff_ratio",
    "ln_assets", "roa", "firm_age", "cashflow_ratio", "ln_rd_subsidy",
    "ln_total_subsidy", "province_sci_tech_ratio", "province_rd_intensity",
    "did_x_prov_sci_tech"]
    if c in S_2017_2024.columns]
desc = S_2017_2024[desc_vars].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).T
desc.to_csv(OUT / "v4_descriptive_statistics.csv", encoding="utf-8-sig")

# ============================================================
# 6. 实证报告
# ============================================================
print("\n" + "=" * 80)
print("6. 生成实证报告")
print("=" * 80)

rpt = []
rpt.append("# 科技自主创新政策实证研究 — v4 报告\n")
rpt.append(f"## 数据概况\n")
rpt.append(f"- v4 扩展样本 (2017-2024): {len(S_2017_2024):,} obs × {S_2017_2024['stock_code'].nunique():,} firms")
rpt.append(f"- v3 基准样本 (2017-2022): {len(S_2017_2022):,} obs × {S_2017_2022['stock_code'].nunique():,} firms")
rpt.append(f"- 制造业占比: {S_2017_2024['manufacturing'].mean():.1%}")
rpt.append(f"- 省份覆盖率: {S_2017_2024['province_clean'].notna().mean():.1%}")
rpt.append("")

for bucket, fname in BUCKETS.items():
    fpath = OUT / fname
    if not fpath.exists():
        continue
    df_r = pd.read_csv(fpath)
    rpt.append(f"## {bucket}\n")
    did_rows = df_r[df_r["variable"].str.contains("manufacturing_post|did_x|event_|JOINT|high_sci", na=False)]
    if len(did_rows):
        rpt.append("| Model | Variable | Coef | SE | p | N |")
        rpt.append("|-------|----------|------|-----|---|--|")
        for _, row in did_rows.iterrows():
            coef = f"{row['coef']:.4f}" if pd.notna(row.get('coef')) else "N/A"
            se = f"{row['std_err']:.4f}" if pd.notna(row.get('std_err')) else "N/A"
            p = f"{row['p_value']:.4f}" if pd.notna(row.get('p_value')) else "N/A"
            sig = ""
            if pd.notna(row.get('p_value')):
                pv = row['p_value']
                sig = " ***" if pv < 0.01 else " **" if pv < 0.05 else " *" if pv < 0.1 else ""
            rpt.append(f"| {row['model']} | {row['variable']} | {coef}{sig} | {se} | {p} | {row.get('nobs','')} |")
        rpt.append("")
    else:
        rpt.append("无结果\n")

rpt.append("## v4 新增分析\n")
rpt.append("- **省级财政交互**: DID × 省财政科技支出占比，检验地方财政科技投入的调节效应")
rpt.append("- **时间窗口扩展**: 从 2017-2022 扩展到 2017-2024，捕捉政策的长期效应")
rpt.append("- **2023年稀释控制**: 加入 post2023 虚拟变量控制全行业100%加计扣除的稀释效应")

with open(OUT / "v4_empirical_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(rpt))

# ============================================================
# 7. 关键结果摘要
# ============================================================
print("\n" + "=" * 80)
print("7. 关键结果摘要")
print("=" * 80)

for bucket in ["baseline", "provincial_fiscal", "mechanism", "placebo"]:
    tables = all_res.get(bucket, [])
    if not tables:
        continue
    df_r = pd.concat(tables, ignore_index=True)
    key_vars = df_r[df_r["variable"].str.contains(
        "manufacturing_post2021|did_x_prov_sci_tech|did_x_high_sci_prov|did_x_prov_rd|did_x_ln_prov", na=False)]
    if len(key_vars):
        print(f"\n  [{bucket}]")
        for _, r in key_vars.iterrows():
            sig = "***" if r["p_value"] < 0.01 else "**" if r["p_value"] < 0.05 else "*" if r["p_value"] < 0.1 else ""
            print(f"  {r['model']:35s} {r['variable']:35s} "
                  f"coef={r['coef']:.4f}  se={r['std_err']:.4f}  p={r['p_value']:.4f}{sig}  n={int(r.get('nobs',0)):,}")

elapsed = time.time() - T0
print(f"\n总运行时间: {elapsed:.1f}s ({elapsed/60:.1f}min)")

print(f"\n所有输出: {OUT}/")
for f in sorted(os.listdir(OUT)):
    print(f"  {f}")

print("\nDONE: v4 模型全部完成")
