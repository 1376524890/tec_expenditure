# V6 效率分析 — 数据审计报告

## 面板唯一性

- 全样本: 41,132 obs x 5,716 firms
- 2017-2022: dup=0
- 2017-2024: dup=0
- 2017-2020: dup=0
- 2016-2022: dup=0

**最终面板为唯一企业年度面板，不存在 stock_code-year 重复观测。**

## 变量尺度

- rd_intensity, rd_staff_ratio, province_sci_tech_ratio, province_rd_intensity: /100 (百分比→0-1)
- rd_expense: 元, 同时生成万元/百万元口径
- 专利: 非负整数, log(1+x)
- 缩尾: 按年 1%/99%

## 关键变量覆盖率 (2017-2022)

- ln_invention_apply: 100.0%
- ln_rd_expense_10k: 100.0%
- ln_rd_staff: 100.0%
- eff_invention_apply_rd_10k: 100.0%
- ln_assets: 100.0%
- roa: 100.0%
- cashflow_ratio: 100.0%
- firm_age: 96.5%
- manufacturing: 100.0%
- soe: 94.0%