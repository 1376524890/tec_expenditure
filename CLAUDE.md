# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chinese S&T (科技) innovation policy empirical research project. It collects provincial R&D expenditure data from China's National Bureau of Statistics (NBS) via browser automation, then runs panel fixed-effects models (DID) to evaluate the impact of the **2021 manufacturing R&D expense super-deduction policy** (研发费用加计扣除比例从75%提高至100%).

**Stack**: Python 3.12, uv package manager, pandas/statsmodels/linearmodels for econometrics, Playwright + browser-use for web scraping.

## Key Commands

```bash
# Install dependencies
uv sync

# Build the firm-level analysis panel from raw CSMAR data
uv run python merge_final.py

# Compile provincial R&D expenditure data into provincial panel
uv run python compile_rd_data.py

# Run all econometric models (DID, mechanism, robustness, event study)
uv run python run_final_policy_models.py \
  --data data/firm_panel_final.xlsx \
  --province data/provincial_panel_full.csv \
  --out outputs

# If main table already contains provincial variables, omit --province:
uv run python run_final_policy_models.py --data data/firm_panel_final.xlsx --out outputs
```

## Architecture & Data Flow

```
Raw CSMAR data (data/实证数据.xlsx, 8 sheets)
    │
    ├── merge_final.py ──► data/firm_panel_final.xlsx     (1,666 firms × 2019-2024)
    │
    └── compile_rd_data.py ──► data/provincial_panel_full.csv  (31 provinces × 2011-2024)
                                      │
                                      ▼
                        run_final_policy_models.py
                                      │
                                      ▼
                                  outputs/
                                  ├── 00_data_audit.json
                                  ├── 02_baseline_results.csv
                                  ├── 03_mechanism_results.csv
                                  ├── 04_robustness_results.csv
                                  ├── 05_event_study_results.csv
                                  ├── 06_validity_checks.md
                                  └── 07_full_model_summaries.txt
```

**Web scraping scripts** (data acquisition, not part of the main pipeline):
- `collect_rd_playwright.py` — Playwright-based scraping of NBS data browser and statistical yearbooks for provincial R&D data
- `browser_open.py` — Uses `browser-use` with DeepSeek LLM to automate NBS data collection
- `search_library.py` — Uses `browser-use` with CDP to search library databases (CSMAR, CNRDS, etc.)
- `interactive_browser.py` — Opens a visible Playwright browser to explore statistical yearbook pages interactively

## Econometric Design (run_final_policy_models.py)

- **Core DID specification**: `ln_patent_stock ~ manufacturing_post2021 + controls + firm FE + year FE`, clustered SE by firm
- **Treatment group**: manufacturing firms (`manufacturing=1`), **control group**: non-manufacturing
- **Policy shock**: post-2021 (100% super-deduction for manufacturing)
- **Sample**: 2019-2024, ~1,666 firms (1,133 manufacturing)
- **Engine**: `linearmodels.PanelOLS` with fallback to `statsmodels` OLS with firm/year dummies
- Runs 10 models: baseline DID (3 variants), mechanism (rd_intensity, subsidy, fiscal interaction), robustness (alt timing, asinh outcome, drop 2024), event study

## Important Constraints

- **Never** treat `rd_expense_est` as actual R&D expense — it's estimated from tax deduction data
- **Never** claim strict causal identification — only 2 pre-policy years (2019-2020), insufficient for parallel trends validation
- `ln_rd_tax_deduction_w` is intentionally NOT winsorized (99.8% zeros, winsorization destroys all variation)
- The event study uses 2020 as baseline with only one pre-period coefficient (`event_m2` = 2019)
- `province_std` coverage is ~48%; provincial fiscal interaction models are sub-sample results only

## Sensitive Files

`browser_open.py` contains a hardcoded DeepSeek API key. Do not commit this file without removing the key first.
