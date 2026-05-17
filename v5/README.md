# V5: 科技自主创新政策实证研究 — 探索性方向筛选

## 概述

V5 是对研发费用加计扣除政策效果的**系统性探索性方向筛选**。在严格数据预处理和规范建模的前提下，比较了**14个理论合理的研究方向**，通过 Benjamini-Hochberg 多重检验调整和理论/稳健性双维度评分，筛选最具实证价值和政策解释力的论文主线。

## 数据

### 输入
- `data/firm_panel_v4.csv` — v4 企业面板 (CSMAR 8表合并 + 省级数据)
- `data/provincial_panel_full.csv` — 省级R&D/财政数据

### v5 预处理后数据
- `v5/data/v5_clean_panel.csv` — 41,132 obs × 94 cols × 5,716 firms (2016-2024)

### 预处理要点
| 步骤 | 说明 |
|------|------|
| 比率转换 | rd_intensity, rd_staff_ratio, province_sci_tech_ratio, province_rd_intensity 从百分比(0-100)转换为比率(0-1) (÷100) |
| 缩尾 | 按年 1%/99% winsorize (15个连续变量) |
| 标准化 | z-score 标准化关键变量 (pre_rd_intensity, policy_exposure, tax_saving_est, province_sci_tech_ratio, province_rd_intensity) |
| 变量构造 | 创新效率、滞后产出、四分位、高暴露处理组、交互项 |
| 主键确认 | stock_code-year 无重复 ✓ |

## 14个探索方向

| # | 方向 | 模型数 | 结果 | 推荐 |
|---|------|--------|------|------|
| 1 | 平均政策效应 (DID) | 8 | 全部不显著 | ❌ |
| 2 | 政策暴露强度 | 4 | 2017-2022显著 (BH通过) | ⚠ 次要 |
| 3 | 研发基础四分位 | 5 | 全部不显著 | ❌ |
| 4 | 高研发暴露处理组 | 3 | 全部不显著 | ❌ |
| **5** | **创新效率** | **4** | **全部高度显著 (BH通过)** | **✅ 主线** |
| 6 | 滞后创新产出 | 4 | BH未通过 | ❌ |
| 7 | 政策普惠化阶段 | 7 | 部分边际显著, BH未通过 | ⚠ 补充 |
| 8 | 高技术制造业 | 2 | 全部不显著 | ❌ |
| 9 | 所有制异质性 | 3 | 全部不显著 | ❌ |
| 10 | 地区财政调节 | 6 | 全部不显著 | ❌ |
| **11** | **研发投入行为** | **4** | **3/4显著 (2通过BH)** | **✅ 机制** |
| 12 | PPML计数模型 | 4 | 生成R/Stata代码 | 待验证 |
| 13 | PSM/IPW-DID | 2 | 不显著 | ❌ |
| 14 | 增强固定效应 | 3 | 不改变结论 | — |

## 核心发现

### 主线: 创新效率 (方向5)

**所有4个效率指标均高度显著 (p<0.001), 全部通过BH多重检验。**

| 效率指标 | DID系数 | p值 | BH-p |
|----------|---------|------|------|
| 发明申请/研发支出 | +0.751 | <0.001 | <0.001 |
| 发明授权/研发支出 | +0.762 | <0.001 | <0.001 |
| 发明申请/研发人员 | +0.173 | 0.001 | 0.005 |
| 发明授权/研发人员 | +0.184 | <0.001 | 0.002 |

**⚠ 重要**: 效率的正向显著主要由研发支出的剧烈相对下降驱动 (DID=-0.773, p<0.001), 而非专利产出增长 (DID=-0.025, p=0.315)。论文必须诚实分解并讨论四种解释机制: 效率提升、会计重分类、对照组效应、结构转型。

### 机制: 研发投入行为 (方向11)

制造业企业在政策后相对非制造业:
- 研发支出下降约54% (p<0.001, BH通过)
- 研发人员下降约18% (p<0.001, BH通过)

## 推荐论文题目

> **研发费用加计扣除政策、研发投入调整与企业创新效率**

核心叙事: "税收激励未扩大创新规模，但可能提升了单位研发投入的产出效率。"

## 文件清单

```
v5/
├── data/
│   └── v5_clean_panel.csv          # v5预处理后面板数据 (41,132 obs)
├── outputs/
│   ├── explore_data_audit.md        # 数据审计报告
│   ├── explore_preprocessing_log.md # 预处理日志
│   ├── explore_missing_rates.csv    # 变量缺失率
│   ├── explore_descriptive_statistics.csv # 描述性统计
│   ├── explore_all_model_comparison.csv   # 全部266个模型结果
│   ├── explore_significant_findings.csv   # BH调整后显著发现
│   ├── explore_full_report.md       # 完整14方向分析报告
│   ├── explore_recommended_research_direction.md # 推荐研究方向
│   ├── explore_full_model_summaries.txt # 全部模型详细输出
│   ├── explore_ppml_r_stata_code.txt    # PPML的R/Stata代码
│   ├── explore_baseline_did.csv     # 方向1: 平均DID
│   ├── explore_policy_exposure.csv  # 方向2: 政策暴露强度
│   ├── explore_rd_quartile.csv      # 方向3: 四分位异质性
│   ├── explore_high_exposure_treatment.csv # 方向4: 高暴露处理组
│   ├── explore_innovation_efficiency.csv  # 方向5: 创新效率 ★
│   ├── explore_lagged_innovation.csv      # 方向6: 滞后创新
│   ├── explore_policy_stage_2023.csv      # 方向7: 普惠化阶段
│   ├── explore_hightech_manufacturing.csv # 方向8: 高技术制造业
│   ├── explore_ownership_heterogeneity.csv # 方向9: 所有制
│   ├── explore_region_interaction.csv    # 方向10: 地区财政调节
│   ├── explore_rd_behavior.csv          # 方向11: 研发行为 ★
│   ├── explore_ppml_results.csv         # 方向12: PPML
│   ├── explore_psm_ipw_results.csv      # 方向13: PSM/IPW
│   └── explore_stronger_fe_results.csv  # 方向14: 增强FE
└── run_explore_v5.py               # v5分析脚本
```

## 运行方式

```bash
# 从项目根目录运行
uv run python v5/run_explore_v5.py

# 或直接
uv run python run_explore_v5.py
```

输出将生成在 `outputs/explore_*` (运行脚本时) 或已在 `v5/outputs/` 中。

## 关键约束

- 不得编造数据
- 不得为显著性删样本/改口径
- 所有模型均记录 (266个规格)
- 多重检验: BH FDR调整
- `tax_saving_est` 为估算值, 非真实税务数据
- 2023-2024 不是清洁DID对照期
- `lev` (资产负债率) 不可得

## 版本历史

| 版本 | 说明 |
|------|------|
| v1-v2 | 原始管道 (已归档) |
| v3 | 8表合并, 严格去重, 5,407 firms |
| v4 | +省级财政交互, 2017-2024扩展 |
| **v5** | **14方向探索性筛选, BH多重检验, 创新效率主线** |
