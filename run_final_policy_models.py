# -*- coding: utf-8 -*-
"""
科技自主创新政策实证研究：按《最终数据清单.md》运行企业面板模型

输入：
  data/firm_panel_final.xlsx 或 --data 指定路径
  可选：data/provincial_panel_full.csv 或 --province 指定路径

输出：
  outputs/00_data_audit.json
  outputs/01_descriptive_statistics.csv
  outputs/02_baseline_results.csv
  outputs/03_mechanism_results.csv
  outputs/04_robustness_results.csv
  outputs/05_event_study_results.csv
  outputs/06_validity_checks.md
  outputs/07_full_model_summaries.txt

注意：
  本脚本不补造数据。缺少关键字段时会在审计文件中列出，并跳过对应模型。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import warnings
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    from linearmodels.panel import PanelOLS
    HAS_LINEARMODELS = True
except Exception:
    HAS_LINEARMODELS = False

import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats


REQUIRED_CORE = [
    "stock_code", "firm_name", "year", "industry_code", "manufacturing",
    "rd_intensity", "rd_tax_deduction", "rd_expense_est", "rd_deduction_rate",
    "patent_stock", "ln_assets", "roa", "lev", "firm_age", "dual_position",
    "post2021", "manufacturing_post2021"
]

OPTIONAL_CORE = [
    "province_std", "gov_subsidy_rd", "post2022", "post2023", "manufacturing_post2022",
    "province_gdp", "province_budget_exp", "province_sci_tech_exp", "sci_tech_exp_ratio",
    "ip_protection_score", "invention_apply", "invention_grant", "tech_market_turnover",
    "revenue", "total_assets", "income_tax_expense", "profit_before_tax", "soe", "rd_staff"
]

NUMERIC_COLS = [
    "year", "manufacturing", "rd_intensity", "rd_tax_deduction", "rd_expense_est",
    "rd_deduction_rate", "gov_subsidy_rd", "patent_stock", "roa", "lev", "firm_age",
    "ln_assets", "dual_position", "post2021", "post2022", "post2023",
    "manufacturing_post2021", "manufacturing_post2022", "province_gdp",
    "province_budget_exp", "province_sci_tech_exp", "sci_tech_exp_ratio",
    "ip_protection_score", "invention_apply", "invention_grant", "tech_market_turnover",
    "revenue", "total_assets", "income_tax_expense", "profit_before_tax", "soe", "rd_staff"
]


def safe_name(x: str) -> str:
    x = str(x).strip()
    x = re.sub(r"[^0-9a-zA-Z_]+", "_", x)
    if re.match(r"^\d", x):
        x = "v_" + x
    return x


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {c: safe_name(c) for c in df.columns}
    return df.rename(columns=mapping)


def read_main_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"找不到主数据文件：{path}")
    if path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError("主数据只支持 .xlsx/.xls/.csv")
    return normalize_columns(df)


def to_numeric_if_exists(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def winsorize_series(s: pd.Series, p: float = 0.01) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    if s.notna().sum() < 20:
        return s
    lo, hi = s.quantile([p, 1 - p])
    return s.clip(lo, hi)


def add_constructed_vars(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    if "manufacturing" not in df.columns and "industry_code" in df.columns:
        df["manufacturing"] = df["industry_code"].astype(str).str.startswith("C").astype(int)

    if "post2021" not in df.columns and "year" in df.columns:
        df["post2021"] = (df["year"] >= 2021).astype(int)
    if "post2022" not in df.columns and "year" in df.columns:
        df["post2022"] = (df["year"] >= 2022).astype(int)
    if "post2023" not in df.columns and "year" in df.columns:
        df["post2023"] = (df["year"] >= 2023).astype(int)

    if "manufacturing_post2021" not in df.columns and {"manufacturing", "post2021"}.issubset(df.columns):
        df["manufacturing_post2021"] = df["manufacturing"] * df["post2021"]
    if "manufacturing_post2022" not in df.columns and {"manufacturing", "post2022"}.issubset(df.columns):
        df["manufacturing_post2022"] = df["manufacturing"] * df["post2022"]

    if "patent_stock" in df.columns:
        df["ln_patent_stock"] = np.log1p(pd.to_numeric(df["patent_stock"], errors="coerce").clip(lower=0))
        df["asinh_patent_stock"] = np.arcsinh(pd.to_numeric(df["patent_stock"], errors="coerce"))

    if "rd_tax_deduction" in df.columns:
        df["ln_rd_tax_deduction"] = np.log1p(pd.to_numeric(df["rd_tax_deduction"], errors="coerce").clip(lower=0))

    if "rd_expense_est" in df.columns:
        df["ln_rd_expense_est"] = np.log1p(pd.to_numeric(df["rd_expense_est"], errors="coerce").clip(lower=0))

    if "gov_subsidy_rd" in df.columns:
        df["gov_subsidy_rd_missing"] = df["gov_subsidy_rd"].isna().astype(int)
        df["gov_subsidy_rd_zero"] = pd.to_numeric(df["gov_subsidy_rd"], errors="coerce").fillna(0)
        df["ln_gov_subsidy_rd"] = np.log1p(df["gov_subsidy_rd_zero"].clip(lower=0))

    # winsorized versions for continuous variables
    cont = [
        "ln_patent_stock", "asinh_patent_stock", "rd_intensity",
        # "ln_rd_tax_deduction" excluded from winsorization: >99% zeros after clip(lower=0),
        # winsorization collapses both tails to 0 → variable destroyed.
        "ln_rd_expense_est", "ln_gov_subsidy_rd", "ln_assets", "roa", "lev", "firm_age",
        "sci_tech_exp_ratio", "province_gdp", "province_budget_exp", "province_sci_tech_exp",
        "ip_protection_score", "tech_market_turnover", "invention_apply", "invention_grant"
    ]
    for c in cont:
        if c in df.columns:
            df[c + "_w"] = winsorize_series(df[c])

    # ln_rd_tax_deduction_w: explicitly NOT winsorized (see cont list exclusion above).
    # >99% values are 0 after clip(lower=0); winsorization destroys all variation.
    if "ln_rd_tax_deduction" in df.columns:
        df["ln_rd_tax_deduction_w"] = df["ln_rd_tax_deduction"].copy()

    # lagged policy intensity variables
    if {"stock_code", "year", "ln_rd_tax_deduction_w"}.issubset(df.columns):
        df = df.sort_values(["stock_code", "year"])
        df["ln_rd_tax_deduction_l1"] = df.groupby("stock_code")["ln_rd_tax_deduction_w"].shift(1)

    return df


def audit_data(df: pd.DataFrame, out_dir: Path) -> Dict:
    missing_required = [c for c in REQUIRED_CORE if c not in df.columns]
    missing_optional = [c for c in OPTIONAL_CORE if c not in df.columns]

    dup_n = 0
    if {"stock_code", "year"}.issubset(df.columns):
        dup_n = int(df.duplicated(["stock_code", "year"]).sum())

    miss_rates = {c: float(df[c].isna().mean()) for c in df.columns}
    cover = {}
    for c in REQUIRED_CORE + OPTIONAL_CORE:
        if c in df.columns:
            cover[c] = round(1 - float(df[c].isna().mean()), 4)
        else:
            cover[c] = None

    audit = {
        "n_rows": int(len(df)),
        "n_firms": int(df["stock_code"].nunique()) if "stock_code" in df.columns else None,
        "years": sorted([int(x) for x in df["year"].dropna().unique()]) if "year" in df.columns else [],
        "duplicates_stock_year": dup_n,
        "missing_required_columns": missing_required,
        "missing_optional_columns": missing_optional,
        "coverage_by_requested_field": cover,
        "key_warnings": [],
    }

    if audit["years"]:
        if min(audit["years"]) > 2019:
            audit["key_warnings"].append("样本未覆盖2019年前，无法做2021政策前的充分趋势检验。")
        if min(audit["years"]) > 2015:
            audit["key_warnings"].append("样本未覆盖2015年前后，不能识别2015政策效果。")
        if min(audit["years"]) > 2018:
            audit["key_warnings"].append("样本未覆盖2018年前后，不能识别2018政策效果。")

    if "province_std" in df.columns and df["province_std"].notna().mean() < 0.8:
        audit["key_warnings"].append("省份匹配率低于80%，涉及省级财政变量的模型只能作为子样本分析。")
    if "gov_subsidy_rd" in df.columns and df["gov_subsidy_rd"].notna().mean() < 0.8:
        audit["key_warnings"].append("研发补助变量缺失率较高，补贴机制检验需使用缺失指示变量或子样本稳健性。")

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "00_data_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)

    pd.DataFrame({
        "variable": list(miss_rates.keys()),
        "missing_rate": list(miss_rates.values())
    }).sort_values("missing_rate", ascending=False).to_csv(out_dir / "00_missing_rates.csv", index=False, encoding="utf-8-sig")

    return audit


def descriptive_stats(df: pd.DataFrame, out_dir: Path) -> None:
    vars_for_desc = [
        "patent_stock", "ln_patent_stock", "rd_intensity", "rd_tax_deduction", "ln_rd_tax_deduction",
        "rd_expense_est", "gov_subsidy_rd", "ln_assets", "roa", "lev", "firm_age",
        "sci_tech_exp_ratio", "ip_protection_score", "tech_market_turnover"
    ]
    vars_for_desc = [c for c in vars_for_desc if c in df.columns]
    if vars_for_desc:
        desc = df[vars_for_desc].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).T
        desc.to_csv(out_dir / "01_descriptive_statistics.csv", encoding="utf-8-sig")

    if {"manufacturing", "year"}.issubset(df.columns):
        tab = df.groupby(["year", "manufacturing"]).size().unstack(fill_value=0)
        tab.to_csv(out_dir / "01_sample_distribution_year_treat.csv", encoding="utf-8-sig")


def available_controls(df: pd.DataFrame, exclude_rd: bool = False) -> List[str]:
    candidates = ["rd_intensity_w", "ln_assets_w", "roa_w", "lev_w", "firm_age_w", "dual_position"]
    if exclude_rd:
        candidates = [c for c in candidates if c != "rd_intensity_w"]
    return [c for c in candidates if c in df.columns]


def run_panel_model(df: pd.DataFrame, y: str, xvars: List[str], model_name: str,
                    entity: str = "stock_code", time: str = "year") -> Optional[Tuple[pd.DataFrame, str]]:
    needed = [y, entity, time] + xvars
    if not set(needed).issubset(df.columns):
        return None
    d = df[needed].dropna().copy()
    if d.empty or d[entity].nunique() < 10 or d[time].nunique() < 2:
        return None

    for c in [y] + xvars:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna()
    if d.empty:
        return None

    # 删除无变化或全缺失解释变量，避免完全共线
    keep_x = []
    for x in xvars:
        if d[x].nunique(dropna=True) > 1 and d[x].std(skipna=True) > 0:
            keep_x.append(x)
    xvars = keep_x
    if not xvars:
        return None

    if HAS_LINEARMODELS:
        pdata = d.set_index([entity, time])
        formula = y + " ~ 1 + " + " + ".join(xvars) + " + EntityEffects + TimeEffects"
        try:
            res = PanelOLS.from_formula(formula, data=pdata, drop_absorbed=True).fit(
                cov_type="clustered", cluster_entity=True
            )
            params = res.params
            bse = res.std_errors
            pvals = res.pvalues
            rows = []
            for v in xvars:
                if v in params.index:
                    rows.append({
                        "model": model_name,
                        "dependent": y,
                        "variable": v,
                        "coef": params[v],
                        "std_err": bse[v],
                        "p_value": pvals[v],
                        "nobs": int(res.nobs),
                        "firms": int(d[entity].nunique()),
                        "years": int(d[time].nunique()),
                        "r2_within": float(res.rsquared_within) if res.rsquared_within is not None else np.nan,
                        "engine": "linearmodels.PanelOLS"
                    })
            return pd.DataFrame(rows), str(res.summary)
        except Exception as e:
            # fallback below
            fallback_error = repr(e)
    else:
        fallback_error = "linearmodels not installed"

    # statsmodels fallback: firm + year dummy OLS, clustered by firm
    try:
        formula = y + " ~ " + " + ".join(xvars) + f" + C({entity}) + C({time})"
        res = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": d[entity]})
        rows = []
        for v in xvars:
            if v in res.params.index:
                rows.append({
                    "model": model_name,
                    "dependent": y,
                    "variable": v,
                    "coef": res.params[v],
                    "std_err": res.bse[v],
                    "p_value": res.pvalues[v],
                    "nobs": int(res.nobs),
                    "firms": int(d[entity].nunique()),
                    "years": int(d[time].nunique()),
                    "r2_within": np.nan,
                    "engine": f"statsmodels OLS dummy FE; PanelOLS fallback reason: {fallback_error}"
                })
        return pd.DataFrame(rows), str(res.summary())
    except Exception as e:
        return None


def run_model_set(df: pd.DataFrame, out_dir: Path) -> Dict[str, pd.DataFrame]:
    summaries = []
    outputs: Dict[str, List[pd.DataFrame]] = {
        "baseline": [],
        "mechanism": [],
        "robustness": [],
        "event_study": [],
    }

    def add_result(bucket: str, result: Optional[Tuple[pd.DataFrame, str]], title: str):
        if result is None:
            return
        table, summary = result
        if table is not None and len(table):
            outputs[bucket].append(table)
            summaries.append("\n" + "=" * 100 + f"\n{title}\n" + summary)

    controls = available_controls(df)
    controls_no_rd = available_controls(df, exclude_rd=True)

    # 1. 基准DID：制造业 × 2021年后
    add_result(
        "baseline",
        run_panel_model(df, "ln_patent_stock_w", ["manufacturing_post2021"] + controls, "M1_DID_2021"),
        "M1_DID_2021: ln_patent_stock ~ manufacturing_post2021 + controls + firm FE + year FE"
    )

    # 2. 加入税收优惠强度，注意解释为强度相关性
    add_result(
        "baseline",
        run_panel_model(df, "ln_patent_stock_w", ["manufacturing_post2021", "ln_rd_tax_deduction_w"] + controls, "M2_DID_tax_intensity"),
        "M2_DID_tax_intensity: add ln_rd_tax_deduction"
    )

    # 3. 滞后一期税收优惠
    if "ln_rd_tax_deduction_l1" in df.columns:
        add_result(
            "baseline",
            run_panel_model(df, "ln_patent_stock_w", ["manufacturing_post2021", "ln_rd_tax_deduction_l1"] + controls, "M3_lag_tax"),
            "M3_lag_tax: lagged ln_rd_tax_deduction"
        )

    # 4. 机制：创新投入
    add_result(
        "mechanism",
        run_panel_model(df, "rd_intensity_w", ["manufacturing_post2021"] + controls_no_rd, "MECH1_RD_intensity"),
        "MECH1_RD_intensity: rd_intensity ~ manufacturing_post2021 + controls + FE"
    )

    # 5. 机制：研发补助，缺失用0并加缺失指示变量
    subsidy_x = ["manufacturing_post2021", "ln_gov_subsidy_rd_w", "gov_subsidy_rd_missing"] + controls
    add_result(
        "mechanism",
        run_panel_model(df, "ln_patent_stock_w", [x for x in subsidy_x if x in df.columns], "MECH2_subsidy_channel"),
        "MECH2_subsidy_channel: add R&D subsidy variable"
    )

    # 6. 省级财政强度交互：只在省级变量可用子样本运行
    if "sci_tech_exp_ratio_w" in df.columns:
        df = df.copy()
        df["did_x_sci_ratio"] = df["manufacturing_post2021"] * df["sci_tech_exp_ratio_w"]
        province_controls = [c for c in ["sci_tech_exp_ratio_w", "ip_protection_score_w", "tech_market_turnover_w"] if c in df.columns]
        add_result(
            "mechanism",
            run_panel_model(df, "ln_patent_stock_w", ["manufacturing_post2021", "did_x_sci_ratio"] + controls + province_controls, "MECH3_local_fiscal_interaction"),
            "MECH3_local_fiscal_interaction: DID × local fiscal science-tech expenditure ratio"
        )

    # 7. 稳健性：2022替代节点
    if "manufacturing_post2022" in df.columns:
        add_result(
            "robustness",
            run_panel_model(df, "ln_patent_stock_w", ["manufacturing_post2022"] + controls, "ROB1_post2022_node"),
            "ROB1_post2022_node: alternative policy timing 2022"
        )

    # 8. 稳健性：asinh替代因变量
    add_result(
        "robustness",
        run_panel_model(df, "asinh_patent_stock_w", ["manufacturing_post2021"] + controls, "ROB2_asinh_outcome"),
        "ROB2_asinh_outcome: asinh patent stock outcome"
    )

    # 9. 稳健性：剔除2024
    if "year" in df.columns:
        df_no2024 = df[df["year"] != 2024].copy()
        add_result(
            "robustness",
            run_panel_model(df_no2024, "ln_patent_stock_w", ["manufacturing_post2021"] + controls, "ROB3_drop_2024"),
            "ROB3_drop_2024: drop 2024 due to missing provincial sci-tech expenditure"
        )

    # 10. 事件研究：2019=-2, 2020=-1基准, 2021=0, 2022=1, 2023=2, 2024=3
    if {"year", "manufacturing"}.issubset(df.columns):
        df = df.copy()
        df["rel_year"] = df["year"].astype(float) - 2021
        event_vars = []
        for k in [-2, 0, 1, 2, 3]:  # omit -1 as baseline
            name = f"event_{'m' + str(abs(k)) if k < 0 else 'p' + str(k)}"
            df[name] = ((df["rel_year"] == k).astype(int) * df["manufacturing"]).astype(float)
            if df[name].sum() > 0:
                event_vars.append(name)
        add_result(
            "event_study",
            run_panel_model(df, "ln_patent_stock_w", event_vars + controls, "EVT_event_study_2021"),
            "EVT_event_study_2021: event-study coefficients, baseline year = 2020"
        )

    # save tables
    result_files = {}
    for bucket, tables in outputs.items():
        if tables:
            table = pd.concat(tables, ignore_index=True)
            result_files[bucket] = table
            fname = {
                "baseline": "02_baseline_results.csv",
                "mechanism": "03_mechanism_results.csv",
                "robustness": "04_robustness_results.csv",
                "event_study": "05_event_study_results.csv",
            }[bucket]
            table.to_csv(out_dir / fname, index=False, encoding="utf-8-sig")
        else:
            result_files[bucket] = pd.DataFrame()

    with open(out_dir / "07_full_model_summaries.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(summaries) if summaries else "No model was successfully estimated.\n")

    return result_files


def validity_checks(df: pd.DataFrame, results: Dict[str, pd.DataFrame], audit: Dict, out_dir: Path) -> None:
    lines = []
    lines.append("# 效度检验与数据审计结论\n")

    lines.append("## 1. 数据完整性\n")
    lines.append(f"- 样本行数：{audit.get('n_rows')}。")
    lines.append(f"- 企业数量：{audit.get('n_firms')}。")
    lines.append(f"- 年份范围：{audit.get('years')}。")
    lines.append(f"- stock_code-year 重复记录：{audit.get('duplicates_stock_year')}。")
    if audit.get("missing_required_columns"):
        lines.append(f"- 缺少必要字段：{audit['missing_required_columns']}。相关模型不应运行。")
    else:
        lines.append("- 必要字段齐全，可运行基准模型。")
    if audit.get("key_warnings"):
        for w in audit["key_warnings"]:
            lines.append(f"- 警告：{w}")

    lines.append("\n## 2. DID识别条件\n")
    lines.append("- 当前政策冲击设定为 2021 年制造业研发费用加计扣除比例提高至100%，处理组为制造业企业，对照组为非制造业企业。")
    lines.append("- 由于样本期为2019-2024，政策前仅2019、2020两个年份。事件研究只能提供非常有限的平行趋势证据，不能声称完成充分的动态趋势检验。")
    lines.append("- 若 `event_m2` 即2019年相对2020年的处理组差异项显著，说明政策前趋势存在差异，应降低因果解释强度。")

    if "event_study" in results and not results["event_study"].empty:
        ev = results["event_study"]
        pre = ev[ev["variable"].str.contains("event_m2", na=False)]
        if len(pre):
            coef = pre.iloc[0]["coef"]
            pval = pre.iloc[0]["p_value"]
            lines.append(f"- 事件研究政策前项 event_m2：coef={coef:.4f}, p={pval:.4g}。")

    lines.append("\n## 3. 稳健性分析规则\n")
    lines.append("- 若基准模型、asinh替代因变量、剔除2024样本后的核心系数方向一致，说明结果较稳健。")
    lines.append("- 若2022替代节点结果与2021节点差异较大，应解释为政策时点敏感，不应过度外推。")
    lines.append("- 省级财政科技支出交互项只基于省份匹配子样本，不能代表全样本。")

    lines.append("\n## 4. 税收优惠强度变量说明\n")
    lines.append("- `rd_tax_deduction` 原始值中 99.8% 为负数，经 clip(lower=0) 和 log1p 转换后，仅约 0.2% 的观测有非零值（nunique=9）。")
    lines.append("- 由于变量极度稀疏，`ln_rd_tax_deduction_w` 不进行 winsorize（winsorize 会使其完全退化为零常量）。")
    lines.append("- M2 和 M3 中该变量的系数仅由 <1% 的非零观测驱动，解释时需极度谨慎，不能推广至全样本。")
    lines.append("- 该变量不可直接解释为'企业享受了加计扣除'，仅反映原始数据中 rd_tax_deduction 为正的极少数情形。")

    lines.append("\n## 5. 禁止性说明\n")
    lines.append("- 不得把 `rd_expense_est` 写成企业真实研发费用。它是由加计扣除额反推的估算变量。")
    lines.append("- 不得把 `rd_tax_deduction` 写成完整税务申报数据，除非原始数据说明确认为实际纳税调减额。")
    lines.append("- 不得把累计专利数解释为当年新增创新产出。当前因变量是存量指标，短期政策响应可能被弱化。")

    with open(out_dir / "06_validity_checks.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="data/firm_panel_final.xlsx", help="主企业面板数据")
    parser.add_argument("--province", type=str, default="data/provincial_panel_full.csv", help="可选省级面板数据；若主表已合并可忽略")
    parser.add_argument("--out", type=str, default="outputs", help="输出目录")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = read_main_data(Path(args.data))
    df = to_numeric_if_exists(df, NUMERIC_COLS)
    df = add_constructed_vars(df)

    # 如果主表没有省级变量且提供省级面板，尝试按 province_std-year 合并
    province_path = Path(args.province)
    if province_path.exists() and "province_std" in df.columns:
        prov = pd.read_csv(province_path) if province_path.suffix.lower() == ".csv" else pd.read_excel(province_path)
        prov = normalize_columns(prov)
        prov = to_numeric_if_exists(prov, NUMERIC_COLS)
        if {"province_std", "year"}.issubset(prov.columns):
            overlap = [c for c in prov.columns if c in df.columns and c not in ["province_std", "year"]]
            prov2 = prov.drop(columns=overlap)
            df = df.merge(prov2, on=["province_std", "year"], how="left")
            df = add_constructed_vars(df)

    if {"stock_code", "year"}.issubset(df.columns):
        df = df.sort_values(["stock_code", "year"])

    audit = audit_data(df, out_dir)
    descriptive_stats(df, out_dir)
    results = run_model_set(df, out_dir)
    validity_checks(df, results, audit, out_dir)

    df.to_csv(out_dir / "clean_panel_for_models.csv", index=False, encoding="utf-8-sig")

    print("DONE: 科技自主创新政策模型已运行。")
    print(json.dumps({
        "rows": audit.get("n_rows"),
        "firms": audit.get("n_firms"),
        "years": audit.get("years"),
        "warnings": audit.get("key_warnings"),
        "output_dir": str(out_dir.resolve()),
        "linearmodels_engine": HAS_LINEARMODELS,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
