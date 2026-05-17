# V5 探索分析 — 数据审计报告

## 面板唯一性

- 2017_2022: dup=0, max_obs=6, firms_exceeding=0, mfg=62.5%
- 2017_2024: dup=0, max_obs=8, firms_exceeding=0, mfg=63.8%
- 2017_2020: dup=0, max_obs=4, firms_exceeding=0, mfg=61.6%
- 2016_2022: dup=0, max_obs=7, firms_exceeding=0, mfg=62.3%

**最终面板为唯一企业年度面板，不存在 stock_code-year 重复观测。**

## 变量尺度转换

- `rd_staff_ratio` (研发人员占比 (→0-1)): median 13.66 → 0.1366 (÷100)
- `province_sci_tech_ratio` (省财政科技支出占比 (→0-1)): median 4.55 → 0.0455 (÷100)
- `province_rd_intensity` (省R&D强度 (→0-1)): median 2.769 → 0.02769 (÷100)

## 缩尾处理 (按年, 1%/99%)

处理变量: roa, cashflow_ratio, rd_intensity, rd_staff_ratio, ln_assets, ln_invention_apply, ln_invention_grant, ln_patent_apply_total, ln_patent_grant_total, ln_rd_expense, ln_rd_staff, ln_rd_subsidy, ln_total_subsidy, ln_tax_saving_est, firm_age, province_sci_tech_ratio, province_rd_intensity

## 最终面板概况

- 全量: 41,132 obs × 5,716 firms
- 2017_2022: 26,772 obs × 5,404 firms, dup=0
- 2017_2024: 37,697 obs × 5,713 firms, dup=0
- 2017_2020: 16,480 obs × 4,638 firms, dup=0
- 2016_2022: 30,207 obs × 5,407 firms, dup=0

**最终面板为唯一企业年度面板。**

## 关键变量覆盖率 (2017-2022, v5预处理后)

| 变量 | 缺失率 | 均值 | 标准差 | Min | Max |
|------|--------|------|--------|-----|-----|
| ln_invention_apply | 0.0% | 0.3957 | 1.118 | 0 | 9.089 |
| ln_invention_grant | 0.0% | 0.3068 | 0.9022 | 0 | 8.093 |
| ln_patent_apply_total | 0.0% | 0.5899 | 1.49 | 0 | 9.737 |
| ln_patent_grant_total | 0.0% | 0.5374 | 1.395 | 0 | 9.503 |
| rd_intensity | 14.7% | 0.05383 | 0.05657 | 0.0002894 | 0.4014 |
| ln_rd_staff | 0.0% | 4.468 | 2.389 | 0 | 11.15 |
| rd_staff_ratio | 18.0% | 0.1703 | 0.1387 | 0.004 | 0.7199 |
| ln_assets | 0.0% | 22.22 | 1.532 | 19.04 | 27.2 |
| roa | 0.0% | 0.04126 | 0.08841 | -0.3514 | 0.2464 |
| firm_age | 3.5% | 20.27 | 5.986 | 7 | 38 |
| cashflow_ratio | 0.0% | 0.04827 | 0.07211 | -0.1718 | 0.252 |
| ln_rd_subsidy | 0.0% | 9.69 | 7.132 | 0 | 21.47 |
| policy_exposure | 16.5% | 0.0126 | 0.03026 | 0 | 0.3182 |
| z_policy_exposure | 16.5% | -0.1259 | 0.8906 | -0.4966 | 8.867 |
| pre_rd_intensity | 16.5% | 0.04861 | 0.04739 | 0.0002894 | 0.3182 |
| province_sci_tech_ratio | 3.6% | 0.03973 | 0.01745 | 0.0054 | 0.0676 |
| province_rd_intensity | 3.6% | 0.02756 | 0.01231 | 0.004319 | 0.06287 |
| manufacturing | 0.0% | 0.6253 | 0.4841 | 0 | 1 |
| soe | 6.0% | 0.0847 | 0.2784 | 0 | 1 |
| hightech_mfg | 0.0% | 0.4099 | 0.4918 | 0 | 1 |
| manufacturing_post2021 | 0.0% | 0.2461 | 0.4307 | 0 | 1 |