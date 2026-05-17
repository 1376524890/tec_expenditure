# 数据预处理日志

## 比率变量转换 (百分比→0-1)

- `rd_intensity` (研发强度 (→0-1)): median 4.065 → 0.04065 (÷100)
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