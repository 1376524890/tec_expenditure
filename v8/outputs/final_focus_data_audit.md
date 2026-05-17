# 数据审计报告

## 样本概况
- 2017-2022 基准样本: 26,772 obs, 5404 firms
- stock_code-year 唯一性: 通过
- 每企业最多观测: 6 条
- 恰好6条企业占比: 3703/5404 (68.5%)

## 2017-2024 扩展样本
- 每企业最多观测: 8 条

## 核心变量缺失率
                   variable missing_rate  n_missing  n_total
0                stock_code       0.0000          0    26772
1                      year       0.0000          0    26772
2           invention_apply       0.0000          0    26772
3           invention_grant       0.0000          0    26772
4        patent_apply_total       0.0000          0    26772
5        patent_grant_total       0.0000          0    26772
6                rd_expense       0.0000          0    26772
7              rd_intensity       0.1473       3943    26772
8          rd_intensity_raw       0.1587       4248    26772
9                  rd_staff       0.0000          0    26772
10           rd_staff_ratio       0.1800       4819    26772
11                ln_assets       0.0000          0    26772
12                      roa       0.0000          1    26772
13           cashflow_ratio       0.0001          2    26772
14                 firm_age       0.0351        941    26772
15            manufacturing       0.0000          0    26772
16                      soe       0.0602       1613    26772
17            industry_code       0.0351        941    26772
18           province_clean       0.0358        959    26772
19         pre_rd_intensity       0.1655       4430    26772
20          policy_exposure       0.1655       4430    26772
21  province_sci_tech_ratio       0.0358        959    26772

## 金额变量单位
所有金额变量 (rd_expense, total_assets, revenue) 单位均为元 (yuan)。
在效率指标构造中将进行单位转换: ln(1 + rd_expense / 10000) → 万元对数。

## 比率变量口径
- `rd_intensity`, `rd_intensity_raw`: 百分比口径 (如 5.44 = 5.44%)，需转换为 0-1 口径
- `rd_staff_ratio`: 百分比口径 (如 13.46 = 13.46%)
- `roa`, `cashflow_ratio`: 已为 0-1 口径

## 缩尾处理
变量可能已在 v3 合并阶段进行了缩尾处理。本分析对新建的比率型效率变量额外进行 1%/99% 缩尾。
原始连续变量使用已缩尾版本。

## 已知限制
- `lev` (资产负债率): CSMAR资产负债表缺少负债数据，不可用。使用 `cashflow_ratio` 作为补充控制。
- `soe` 覆盖率: 94.0%
- `pre_rd_intensity` 覆盖率: 83.5% (无政策前观测的企业缺失)
