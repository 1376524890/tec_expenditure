# 最终数据审计报告

## 面板唯一性确认

- 全样本 (2016-2025): 46,705 obs × 5,834 firms
- 全样本 stock_code-year 重复: **0** (必须为 0)

| 样本 | Obs | Firms | Dup | Max Obs/Firm | Mfg% |
|------|-----|-------|-----|-------------|------|
| 2017-2022 (基准) | 26,772 | 5,404 | 0 | 6 | 62.5% |
| 2017-2024 (扩展) | 37,697 | 5,713 | 0 | 8 | 63.8% |
| 2017-2020 (安慰剂) | 16,480 | 4,638 | 0 | 4 | 61.6% |
| 2016-2022 | 30,207 | 5,407 | 0 | 7 | 62.3% |

**最终面板为唯一企业年度面板，不存在 stock_code-year 重复观测。**

## 关键变量覆盖率 (2017-2022)

| 变量 | 缺失率 | 均值 | 标准差 | Min | Max |
|------|--------|------|--------|-----|-----|
| ln_invention_apply | 0.0% | 0.3881 | 1.08 | 0 | 5.075 |
| ln_invention_grant | 0.0% | 0.2982 | 0.8541 | 0 | 4.344 |
| ln_patent_apply_total | 0.0% | 0.5805 | 1.449 | 0 | 6.028 |
| ln_patent_grant_total | 0.0% | 0.5277 | 1.353 | 0 | 5.713 |
| invention_apply | 0.0% | 9.785 | 157.7 | 0 | 8860 |
| invention_grant | 0.0% | 4.434 | 55.82 | 0 | 3270 |
| rd_intensity | 14.7% | 5.442 | 5.945 | 0.02894 | 40.14 |
| ln_rd_staff | 0.0% | 4.461 | 2.375 | 0 | 8.739 |
| rd_staff_ratio | 18.0% | 17.05 | 13.92 | 0.4 | 71.99 |
| ln_assets | 0.0% | 22.22 | 1.539 | 19.04 | 27.27 |
| roa | 0.0% | 0.041 | 0.08934 | -0.3514 | 0.2464 |
| firm_age | 3.5% | 20.3 | 6.199 | 3 | 68 |
| cashflow_ratio | 0.0% | 0.04824 | 0.07227 | -0.1718 | 0.252 |
| soe | 6.0% | 0.0847 | 0.2784 | 0 | 1 |
| manufacturing | 0.0% | 0.6253 | 0.4841 | 0 | 1 |
| manufacturing_post2021 | 0.0% | 0.2461 | 0.4307 | 0 | 1 |
| ln_rd_subsidy | 0.0% | 9.681 | 7.12 | 0 | 18.09 |
| ln_total_subsidy | 0.0% | 14.7 | 6.209 | 0 | 20.87 |
| policy_exposure | 16.5% | 22 | 1783 | 0 | 1.86e+05 |
| pre_rd_intensity | 16.5% | 37.63 | 2190 | 0.0002266 | 1.86e+05 |
| province_sci_tech_ratio | 3.6% | 3.972 | 1.747 | 0.32 | 6.76 |
| province_rd_intensity | 3.6% | 2.755 | 1.232 | 0.21 | 6.287 |

## 省级变量覆盖率 (2017-2022)

| 变量 | 缺失率 | 均值 |
|------|--------|------|
| province_sci_tech_ratio | 3.6% | 3.972 |
| province_rd_intensity | 3.6% | 2.755 |
| province_sci_tech_exp | 3.6% | 439.3 |
| province_rd_expenditure | 3.6% | 1820 |
| province_gdp | 3.6% | 6.319e+04 |

## 制造业与高技术制造业

- 制造业占比 (2017-2022): 62.5%
- 高技术制造业占比 (of all firms): 41.0%
- 高技术制造业占比 (of manufacturing): 65.5%
- 狭义高技术制造业占比 (of manufacturing): 39.7%
- 高技术行业代码: ['C27', 'C37', 'C38', 'C39', 'C40', 'C26', 'C34', 'C35']

## 控制变量说明

- `lev` (资产负债率): **不可得** — CSMAR 资产负债表仅含 A001000000 (资产总计), 使用 cashflow_ratio 作为补充控制变量
- `firm_age`: 从 EstablishDate 计算, 可能因日期缺失而为 NaN
- `soe`: 来自 HLD_Contrshr.S0702b, controller_type 以 '1' 开头为国有

## 财务数据口径

- 利润表/资产负债表/现金流量表: Typrep=A (合并报表), 仅 12月31日
- 政府补助表: Typrep=1 (合并报表), 关键词匹配研发相关项目
- 专利表: Area=1 (国内专利), 按 stock_code-year-ApplyType 聚合

## 估算变量说明

- `tax_saving_est`: RDSpendSum × rd_deduction_rate × 0.25 — **估算值, 非真实税务数据**
- `policy_exposure`: pre_rd_intensity × manufacturing × post2021 — 外生暴露强度
- `pre_rd_intensity`: 2017-2020 年企业平均 rd_intensity