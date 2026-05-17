# 预处理日志

## 数据来源
- 主面板: data/firm_panel_v4.csv
- 基准样本: 2017-2022, 26,772 obs

## 变量处理

### 比率变量转换 (百分比 → 0-1)
- rd_intensity_01 = rd_intensity / 100
- rd_staff_ratio_01 = rd_staff_ratio / 100

### 研发投入对数 (万元口径)
- ln_rd_expense_10k = ln(1 + rd_expense / 10000)

### 创新数量对数
- ln_invention_apply = ln(1 + invention_apply)
- ln_invention_grant = ln(1 + invention_grant)
- ln_patent_apply_total = ln(1 + patent_apply_total)
- ln_patent_grant_total = ln(1 + patent_grant_total)

### 研发投入对数
- ln_rd_staff = ln(1 + rd_staff)

### 效率变量 (对数差分)
- eff_apply_rd_10k = ln_invention_apply - ln_rd_expense_10k
- eff_grant_rd_10k = ln_invention_grant - ln_rd_expense_10k
- eff_apply_staff = ln_invention_apply - ln_rd_staff
- eff_grant_staff = ln_invention_grant - ln_rd_staff

### 替代效率变量 (比率型)
- apply_per_rd = invention_apply / rd_expense (分母 ≤ 0 → NaN)
- grant_per_rd = invention_grant / rd_expense
- apply_per_staff = invention_apply / rd_staff
- grant_per_staff = invention_grant / rd_staff
- 比率型变量 1%/99% 缩尾后计算 asinh 版本

### 政策前研发基础
- pre_rd_intensity: 企业 2017-2020 年 rd_intensity_01 均值
- high_pre_rd: pre_rd_intensity > median
- high_pre_rd_q4: pre_rd_intensity > p75

### 阶段变量
- treat_2021_2022 = manufacturing × 1[2021 ≤ year ≤ 2022]
- treat_2023_2024 = manufacturing × 1[year ≥ 2023]

## 缩尾
比率型效率变量 (apply_per_rd, grant_per_rd, apply_per_staff, grant_per_staff): 1%/99% 缩尾

## 执行时间
2026-05-17 20:44:35.223263
