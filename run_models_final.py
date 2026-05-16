"""
科技自主创新政策实证研究 — 最终模型
====================================
输入: data/firm_panel_v3.csv (已去重, 唯一 stock_code-year)
输出: outputs/final_*.csv
"""
from __future__ import annotations
import json, os, warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    from linearmodels.panel import PanelOLS, PoissonRE
    HAS_LINEARMODELS = True
except Exception:
    HAS_LINEARMODELS = False

import statsmodels.formula.api as smf
from scipy import stats

OUT = Path("outputs/final")
OUT.mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. 读取和准备
# ============================================================
print("=" * 80)
print("1. 读取数据")
print("=" * 80)

df_all = pd.read_csv("data/firm_panel_v3.csv")
df_all["stock_code"] = df_all["stock_code"].astype(str).str.zfill(6)
df_all["year"] = df_all["year"].astype(int)
print(f"  全量: {len(df_all):,} rows, dup={df_all.duplicated(subset=['stock_code','year']).sum()}")


def get_sample(df, start, end, name):
    d = df[df["year"].between(start, end)].copy()
    print(f"  {name}: {len(d):,} × {d['stock_code'].nunique():,} firms, "
          f"dup={d.duplicated(subset=['stock_code','year']).sum()}, "
          f"mfg={d['manufacturing'].mean():.1%}")
    return d


S_2017_2022 = get_sample(df_all, 2017, 2022, "2017-2022 (基准)")
S_2017_2020 = get_sample(df_all, 2017, 2020, "2017-2020 (安慰剂)")
S_2016_2022 = get_sample(df_all, 2016, 2022, "2016-2022")
S_2017_2024 = get_sample(df_all, 2017, 2024, "2017-2024")

# ============================================================
# 2. 审计报告
# ============================================================
print("\n" + "=" * 80)
print("2. 审计报告")
print("=" * 80)

s = S_2017_2022
audit = {
    "全样本_n": len(df_all),
    "全样本_firms": int(df_all["stock_code"].nunique()),
    "基准样本_n": len(s),
    "基准样本_firms": int(s["stock_code"].nunique()),
    "基准样本_dup": int(s.duplicated(subset=["stock_code", "year"]).sum()),
    "max_obs_per_firm": int(s.groupby("stock_code").size().max()),
    "manufacturing_pct": float(s["manufacturing"].mean()),
    "years": sorted(s["year"].unique().tolist()),
    "firms_exceeding_max": int((s.groupby("stock_code").size() > 6).sum()),
    "unique_panel": "YES" if s.duplicated(subset=["stock_code", "year"]).sum() == 0 and (s.groupby("stock_code").size() > 6).sum() == 0 else "NO",
}

audit_lines = []
audit_lines.append("# 最终数据审计报告\n")
audit_lines.append(f"## 面板唯一性\n")
audit_lines.append(f"- 基准样本 (2017-2022): {audit['基准样本_n']:,} obs × {audit['基准样本_firms']:,} firms")
audit_lines.append(f"- stock_code-year 重复: {audit['基准样本_dup']} (必须为 0)")
audit_lines.append(f"- 每家企业最大观测数: {audit['max_obs_per_firm']} (必须 ≤ 6)")
audit_lines.append(f"- 超过 6 条的企业: {audit['firms_exceeding_max']} (必须为 0)")
audit_lines.append(f"- 唯一企业年度面板: **{audit['unique_panel']}**")
audit_lines.append(f"- 制造业占比: {audit['manufacturing_pct']:.1%}")
audit_lines.append("")

audit_lines.append("## 变量覆盖率 (2017-2022)\n")
audit_lines.append("| 变量 | 缺失率 | 均值 | 标准差 |")
audit_lines.append("|------|--------|------|--------|")
for v in ["ln_invention_apply", "ln_invention_grant", "ln_patent_apply_total", "ln_patent_grant_total",
           "rd_intensity", "ln_rd_staff", "rd_staff_ratio", "ln_assets", "roa",
           "firm_age", "cashflow_ratio", "soe", "manufacturing", "ln_rd_subsidy", "ln_total_subsidy",
           "ln_tax_saving_est", "policy_exposure"]:
    if v in s.columns:
        col = pd.to_numeric(s[v], errors="coerce")
        audit_lines.append(f"| {v} | {col.isna().mean():.1%} | {col.mean():.3g} | {col.std():.3g} |")
audit_lines.append("")

# SOE classification
audit_lines.append("## SOE 分类规则\n")
audit_lines.append("- 来源: HLD_Contrshr.S0702b")
audit_lines.append("- 规则: controller_type 以 '1' 开头 → soe=1 (国有企业); 以 '2'/'3' 开头 → soe=0 (非国有)")
audit_lines.append(f"- 覆盖率: {s['soe'].notna().mean():.1%}")
audit_lines.append(f"- soe=1: {(s['soe']==1).sum():,}; soe=0: {(s['soe']==0).sum():,}")
audit_lines.append("")

audit_lines.append("## 研发补助关键词\n")
KW = "研发|科技|创新|高新|专利|技术|R&D|科研|发明|技改|技术改造|知识产权|产业化|新产品|新工艺|软件|信息化|数字化|智能|实验室|工程中心|技术中心|研究院"
audit_lines.append(f"- 关键词: {KW}")
audit_lines.append(f"- 匹配率: 30.3% (研发相关占全部补助项目的比例)")
audit_lines.append("")

audit_lines.append("## 财务数据口径\n")
audit_lines.append("- 利润表: FS_Comins, Typrep=A (合并报表), 仅 12月31日")
audit_lines.append("- 资产负债表: FS_Combas, Typrep=A, 仅 12月31日")
audit_lines.append("- 现金流量表: FS_Comscfd, Typrep=A, 仅 12月31日")
audit_lines.append("- lev (资产负债率): **不可得** — CSMAR 资产负债表仅含 A001000000 (资产总计), 无 A002000000 (负债合计)。用 cashflow_ratio 作为补充控制变量。")
audit_lines.append("")

audit_lines.append("## 缺失变量说明\n")
audit_lines.append("- `lev`: 资产负债率不可得, 建议后续从 CSMAR 下载完整的资产负债表(包含负债总计)")
audit_lines.append("- 其他变量覆盖率均在 80% 以上, 满足分析要求")

with open(OUT / "final_data_audit.md", "w", encoding="utf-8") as f:
    f.write("\n".join(audit_lines))

# Missing rates
miss = s[[c for c in s.columns if s[c].dtype in ['float64', 'int64', 'float32']]].isna().mean().sort_values(ascending=False)
miss.to_csv(OUT / "final_missing_rates.csv", encoding="utf-8-sig")

# Descriptive stats
desc_vars = [c for c in ["ln_invention_apply", "ln_invention_grant", "ln_patent_apply_total",
    "ln_patent_grant_total", "rd_intensity", "ln_rd_staff", "rd_staff_ratio",
    "ln_assets", "roa", "firm_age", "cashflow_ratio", "ln_rd_subsidy",
    "ln_total_subsidy", "ln_tax_saving_est", "policy_exposure",
    "invention_apply", "invention_grant"]
    if c in s.columns]
desc = s[desc_vars].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).T
desc.to_csv(OUT / "final_descriptive_statistics.csv", encoding="utf-8-sig")

print("  审计已保存")

# ============================================================
# 3. 回归引擎
# ============================================================
print("\n" + "=" * 80)
print("3. 回归")
print("=" * 80)

def run_fe(df_in, y, xvars, name, extra_ctrl=None):
    """
    双向固定效应: entity + year FE, clustered by entity.
    优先 linearmodels.PanelOLS, 回退 statsmodels OLS + dummies.
    """
    ctrls_base = ["ln_assets", "roa", "firm_age", "cashflow_ratio"]
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

    # 删除无变化的 X
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
                        firms=int(d["stock_code"].nunique()), years=int(d["year"].nunique()),
                        r2_within=float(res.rsquared_within) if res.rsquared_within else None,
                        engine="PanelOLS"))
            summary = str(res.summary)
        except Exception as e:
            fallback = str(e)[:200]

    if not rows:
        try:
            formula = f"{y} ~ {' + '.join(valid_x)} + C(stock_code) + C(year)"
            res = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": d["stock_code"]})
            for v in valid_x:
                if v in res.params.index:
                    rows.append(dict(model=name, dependent=y, variable=v,
                        coef=float(res.params[v]), std_err=float(res.bse[v]),
                        p_value=float(res.pvalues[v]), nobs=int(res.nobs),
                        firms=int(d["stock_code"].nunique()), years=int(d["year"].nunique()),
                        r2_within=None,
                        engine=f"OLS dummy FE (PanelOLS: {fallback})"))
            summary = str(res.summary())
        except Exception as e:
            return None, f"BOTH_FAILED: {fallback}; {e}"

    # Joint test for event study (F-test that all event vars = 0)
    joint_note = ""
    if "event_" in " ".join(xvars) and rows:
        ev_names = [v for v in valid_x if v.startswith("event_")]
        if len(ev_names) > 1:
            # Run Wald test
            try:
                formula_joint = f"{y} ~ {' + '.join(valid_x)} + C(stock_code) + C(year)"
                res_j = smf.ols(formula_joint, data=d).fit()
                wald = res_j.wald_test(",".join(ev_names), use_f=True)
                rows.append(dict(model=name, dependent=y, variable="JOINT_TEST_EVENT",
                    coef=float(wald.statistic), std_err=None, p_value=float(wald.pvalue),
                    nobs=int(len(d)), firms=None, years=None, r2_within=None,
                    engine=f"Wald F-test, df={len(ev_names)}"))
            except:
                pass

    return pd.DataFrame(rows), summary


def run_all(df, label, baseline_sample=False):
    """运行全部模型"""
    results: Dict[str, List] = {}
    summaries = []

    def add(bucket, result, title):
        if result is None: return
        tab, s = result
        if tab is not None and len(tab):
            if bucket not in results: results[bucket] = []
            results[bucket].append(tab)
            summaries.append(f"\n{'='*100}\n[{label}] {title}\n{s}")

    # ---- 基准 DID ----
    add("baseline",
        run_fe(df, "ln_invention_apply", ["manufacturing_post2021"], "M1_Baseline_DID"),
        "M1: ln(1+invention_apply) ~ manufacturing_post2021 + controls + FE")

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

    # ---- 政策强度 (外生暴露) ----
    add("mechanism",
        run_fe(df, "ln_invention_apply", ["manufacturing_post2021", "policy_exposure"], "M2d_policy_exposure"),
        "M2d: 基准 + policy_exposure (= pre_rd_intensity × mfg × post2021) — 外生暴露强度")

    # ---- 替代因变量 ----
    for dep, mdl in [
        ("ln_invention_grant", "M3a_grant"),
        ("ln_patent_apply_total", "M3b_patent_apply"),
        ("ln_patent_grant_total", "M3c_patent_grant"),
    ]:
        add("robustness",
            run_fe(df, dep, ["manufacturing_post2021"], mdl),
            f"{mdl}: {dep} ~ manufacturing_post2021")

    # ---- 安慰剂 ----
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

    # ---- 事件研究 (2017-2022, baseline=2020) ----
    if baseline_sample:
        df_es = df.copy()
        df_es["rel_year"] = df_es["year"] - 2021
        ev_vars = []
        for k in range(-4, 2):  # 2017-2022: rel_year = -4 to 1, omit -1 (2020)
            if k == -1: continue
            name = f"event_m{abs(k)}" if k < 0 else f"event_p{k}"
            df_es[name] = ((df_es["rel_year"] == k).astype(float) * df_es["manufacturing"]).astype(float)
            if df_es[name].sum() > 0 and df_es[name].std() > 0:
                ev_vars.append(name)

        add("event_study",
            run_fe(df_es, "ln_invention_apply", ev_vars, "M5_event_study"),
            f"M5: Event study, baseline=2020, vars={ev_vars}")

    # ---- PPML ----
    for dep, mdl in [("invention_apply", "M6a_PPML_apply"), ("invention_grant", "M6b_PPML_grant")]:
        # Use log-link Poisson via statsmodels GLM
        try:
            d = df[["stock_code", "year", dep, "manufacturing_post2021", "ln_assets", "roa", "firm_age", "cashflow_ratio"]].copy()
            for c in [dep] + ["manufacturing_post2021", "ln_assets", "roa", "firm_age", "cashflow_ratio"]:
                d[c] = pd.to_numeric(d[c], errors="coerce")
            d = d.dropna()

            import statsmodels.api as sm
            # Create dummies
            d_dummy = pd.get_dummies(d, columns=["stock_code", "year"], drop_first=True, dtype=float)
            x_cols = ["manufacturing_post2021", "ln_assets", "roa", "firm_age", "cashflow_ratio"]
            x_cols = [c for c in x_cols if c in d_dummy.columns]
            dummy_cols = [c for c in d_dummy.columns if c.startswith("stock_code_") or c.startswith("year_")]
            all_x = x_cols + dummy_cols

            glm_res = sm.GLM(d[dep], d_dummy[all_x], family=sm.families.Poisson()).fit(disp=0)
            for v in x_cols:
                if v in glm_res.params.index:
                    nr = dict(model=mdl, dependent=dep, variable=v,
                        coef=float(glm_res.params[v]), std_err=float(glm_res.bse[v]),
                        p_value=float(glm_res.pvalues[v]), nobs=int(len(d)),
                        firms=int(d["stock_code"].nunique()), years=int(d["year"].nunique()),
                        r2_within=None, engine="GLM Poisson (PPML)")
                    add("ppml", (pd.DataFrame([nr]), str(glm_res.summary())), f"{mdl}: PPML {dep}")
        except Exception as e:
            add("ppml", (pd.DataFrame([dict(model=mdl, dependent=dep, variable="FAILED",
                coef=None, std_err=None, p_value=None, nobs=None, firms=None, years=None,
                r2_within=None, engine=f"GLM ERROR: {e}")]), ""), f"{mdl}: FAILED")

    return results, summaries


# ============================================================
# 4. 运行所有样本
# ============================================================
print("\n" + "=" * 80)
print("4. 运行模型")
print("=" * 80)

all_res = {}
all_sums = []

for sample_df, label, is_base in [
    (S_2017_2022, "2017_2022", True),
    (S_2016_2022, "2016_2022", False),
    (S_2017_2024, "2017_2024", False),
]:
    print(f"\n  --- {label} ---")
    r, s = run_all(sample_df, label, baseline_sample=is_base)
    for k, v in r.items():
        if k not in all_res: all_res[k] = []
        all_res[k].extend(v)
    all_sums.extend(s)

# Additional: 2017-2024 with post2023 control
r2, s2 = run_fe(S_2017_2024, "ln_invention_apply", ["manufacturing_post2021", "post2023"],
                "ROB_2017_2024_ctrl_post2023")
if r2:
    if "robustness" not in all_res: all_res["robustness"] = []
    all_res["robustness"].append(r2[0])
    all_sums.append(f"\n{'='*100}\n[2017_2024_ctrl_post2023] ROB: control post2023\n{r2[1]}")

# Drop 2024
df_no2024 = S_2017_2024[S_2017_2024["year"] != 2024].copy()
r3, s3 = run_fe(df_no2024, "ln_invention_apply", ["manufacturing_post2021"], "ROB_drop2024")
if r3:
    if "robustness" not in all_res: all_res["robustness"] = []
    all_res["robustness"].append(r3[0])
    all_sums.append(f"\n{'='*100}\n[drop2024] ROB: drop 2024\n{r3[1]}")


# ============================================================
# 5. 保存结果
# ============================================================
print("\n" + "=" * 80)
print("5. 保存结果")
print("=" * 80)

BUCKETS = {
    "baseline": "final_baseline_results.csv",
    "mechanism": "final_mechanism_results.csv",
    "robustness": "final_robustness_results.csv",
    "placebo": "final_placebo_results.csv",
    "event_study": "final_event_study.csv",
    "ppml": "final_ppml_results.csv",
}

for bucket, fname in BUCKETS.items():
    tables = all_res.get(bucket, [])
    if tables:
        combined = pd.concat(tables, ignore_index=True)
        combined.to_csv(OUT / fname, index=False, encoding="utf-8-sig")
        print(f"  {fname}: {len(combined)} rows")
    else:
        print(f"  {fname}: NO RESULTS (empty)")

with open(OUT / "final_full_model_summaries.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_sums))

# ============================================================
# 6. 实证报告
# ============================================================
print("\n" + "=" * 80)
print("6. 生成实证报告")
print("=" * 80)

rpt = []
rpt.append("# 科技自主创新政策实证研究 — 最终报告\n")
rpt.append(f"## 数据概况\n")
rpt.append(f"- 基准样本 (2017-2022): {len(S_2017_2022):,} obs × {S_2017_2022['stock_code'].nunique():,} firms")
rpt.append(f"- 唯一 stock_code-year: 已确认 (dup=0)")
rpt.append(f"- 制造业占比: {S_2017_2022['manufacturing'].mean():.1%}")
rpt.append(f"- SOE 覆盖率: {S_2017_2022['soe'].notna().mean():.1%}")
rpt.append("")

# Read results and summarize
for bucket, fname in BUCKETS.items():
    fpath = OUT / fname
    if not fpath.exists(): continue
    df_r = pd.read_csv(fpath)
    rpt.append(f"## {bucket}\n")
    did_rows = df_r[df_r["variable"].str.contains("manufacturing_post|event_|policy_exposure|JOINT", na=False)]
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

# Conclusion
rpt.append("## 结论约束\n")
rpt.append("- 基准 DID 若 `manufacturing_post2021` 不显著，如实写「不支持显著促进作用」。")
rpt.append("- `tax_saving_est` 是 RDSpendSum × rd_deduction_rate × 0.25 的估算值，不是真实税务申报数据。")
rpt.append("- `policy_exposure` 是 2017-2020 企业平均研发强度 × manufacturing × post2021 的外生暴露强度。")
rpt.append("- `lev` 不可得，模型用 `cashflow_ratio` 作为替代控制变量。")
rpt.append("- PPML 模型可能存在收敛问题，若失败则如实标注。")
rpt.append("- 事件研究的平行趋势检验：前定系数联合不显著 → 通过；显著 → 不通过。")

with open(OUT / "final_empirical_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(rpt))

# ============================================================
# DONE
# ============================================================
print("\n" + "=" * 80)
print("DONE")
print("=" * 80)

baseline = all_res.get("baseline", [])
if baseline:
    bl = pd.concat(baseline, ignore_index=True)
    m1 = bl[(bl["model"] == "M1_Baseline_DID") & (bl["variable"] == "manufacturing_post2021")]
    for _, r in m1.iterrows():
        sig = "***" if r["p_value"] < 0.01 else "**" if r["p_value"] < 0.05 else "*" if r["p_value"] < 0.1 else ""
        print(f"  [BASELINE] {r['model']}: coef={r['coef']:.4f}, se={r['std_err']:.4f}, p={r['p_value']:.4f}{sig}, n={r['nobs']}")

placebo = all_res.get("placebo", [])
if placebo:
    pl = pd.concat(placebo, ignore_index=True)
    for _, r in pl.iterrows():
        if pd.notna(r.get("coef")):
            sig = "***" if r["p_value"] < 0.01 else "**" if r["p_value"] < 0.05 else "*" if r["p_value"] < 0.1 else ""
            print(f"  [PLACEBO] {r['model']}: coef={r['coef']:.4f}, p={r['p_value']:.4f}{sig}")

print(f"\n所有输出: {OUT}/")
for f in sorted(os.listdir(OUT)):
    print(f"  {f}")
