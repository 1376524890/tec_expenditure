# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chinese S&T (科技) innovation policy empirical research project. It merges CSMAR firm-level data into a panel, then runs panel fixed-effects models (DID) to evaluate the impact of the **2021 manufacturing R&D expense super-deduction policy** (研发费用加计扣除比例从75%提高至100%).

**Stack**: Python 3.12, uv package manager, pandas/statsmodels/linearmodels for econometrics, Playwright + browser-use for web scraping.

## Key Commands

```bash
# Install dependencies
uv sync

# Build the firm-level analysis panel from raw CSMAR data (8 tables)
uv run python merge_final_v3.py

# Compile provincial R&D expenditure data into provincial panel
uv run python compile_rd_data.py

# Run all econometric models (DID, mechanism, robustness, event study, PPML)
uv run python run_models_final.py
```

## Architecture & Data Flow (v3 — current)

```
Raw CSMAR data (data/_extract/, 8 tables)
    │
    ├── merge_final_v3.py ──► data/firm_panel_v3.csv     (5,407 firms × 2017-2022 benchmark)
    │
    └── compile_rd_data.py ──► data/provincial_panel_full.csv  (31 provinces × 2011-2024)
                                      │
                                      ▼
                           run_models_final.py
                                      │
                                      ▼
                              outputs/final/
                              ├── final_data_audit.md
                              ├── final_baseline_results.csv
                              ├── final_mechanism_results.csv
                              ├── final_robustness_results.csv
                              ├── final_placebo_results.csv
                              ├── final_event_study.csv
                              ├── final_ppml_results.csv
                              └── final_empirical_report.md
```

**Archived versions** (in `archive/`):
- `archive/v1/` — Original pipeline (1,666 firms × 2019-2024, `patent_stock` outcome)
- `archive/v2/` — First rebuild (broad time range, `invention_apply` outcome)

**Web scraping scripts** (data acquisition, not part of the main pipeline):
- `collect_rd_playwright.py` — Playwright-based scraping of NBS data browser and statistical yearbooks for provincial R&D data
- `browser_open.py` — Uses `browser-use` with DeepSeek LLM to automate NBS data collection
- `search_library.py` — Uses `browser-use` with CDP to search library databases (CSMAR, CNRDS, etc.)
- `interactive_browser.py` — Opens a visible Playwright browser to explore statistical yearbook pages interactively

## Econometric Design (run_models_final.py)

- **Core DID specification**: `ln_invention_apply ~ manufacturing_post2021 + controls + firm FE + year FE`, clustered SE by firm
- **Treatment group**: manufacturing firms (`manufacturing=1`), **control group**: non-manufacturing
- **Policy shock**: post-2021 (100% super-deduction for manufacturing)
- **Sample**: 2017-2022 benchmark, ~5,407 firms (62.5% manufacturing). Also runs 2016-2022 and 2017-2024 for robustness.
- **Engine**: `linearmodels.PanelOLS` with fallback to `statsmodels` OLS with firm/year dummies
- Models: baseline DID, mechanism (rd_intensity, rd_staff, subsidy channel, policy_exposure), robustness (alternative outcomes, placebo 2019/2020, drop 2024, control post2023), event study (2017-2022, baseline=2020), PPML

## CSMAR Data Tables (8 tables in `data/_extract/`)

| Table | Content |
|-------|---------|
| FS_Comins (利润表) | Revenue, profit, income tax |
| FS_Combas (资产负债表) | Total assets |
| FS_Comscfd (现金流量表) | Cash flow |
| STK_LISTEDCOINFOANL (基本信息) | Province, industry, listing date |
| PT_LCDOMFORAPPLY (专利) | Patent applications/grants by type |
| PT_LCRDSPENDING (研发投入) | R&D spending, staff |
| FN_FN056 (政府补助) | Government subsidies with keyword matching |
| HLD_Contrshr (控制人) | SOE classification |

Financial data filtered to: consolidated statements (Typrep=A), Dec 31 only.

## Important Constraints

- **Never** treat `tax_saving_est` as actual tax data — it's `RDSpendSum × rd_deduction_rate × 0.25`
- **Never** treat `rd_expense_est` as actual R&D expense — it's estimated from tax deduction data (v1 only)
- **Never** claim strict causal identification — event study provides parallel trends evidence but cannot fully validate
- `lev` (资产负债率) is **unavailable** — CSMAR balance sheet lacks liability data. Use `cashflow_ratio` as supplementary control.
- `soe` coverage is ~94% in v3; SOE heterogeneity analysis is representative
- The event study uses 2020 as baseline with pre-periods 2017-2019
- `province_std` coverage was ~48% in v1; v3 has province coverage from CSMAR basic info table
- 2023+ all-industry 100% super-deduction dilutes manufacturing_post2021 treatment effect in extended samples

## Sensitive Files

`browser_open.py` contains a hardcoded DeepSeek API key. Do not commit this file without removing the key first.
