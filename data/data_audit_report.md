# 数据审计报告 — 2026-05-16 20:15

## 一、现有主分析数据

### firm_panel_final.csv
- 行数: 4,033, 列数: 34
- 企业数: 1,666
- 年份: [2019, 2020, 2021, 2022, 2023, 2024]

**高缺失率变量 (>30%):**

- `sci_tech_exp_ratio`: 66.6%
- `province_sci_tech_exp`: 66.6%
- `patent_apply_total`: 52.1%
- `ln_gdp_prov`: 52.1%
- `invention_grant`: 52.1%
- `province_gdp`: 52.1%
- `province_budget_exp`: 52.1%
- `tech_market_turnover`: 52.1%
- `ip_protection_score`: 52.1%
- `invention_apply`: 52.1%
- `patent_grant_total`: 52.1%
- `province_std`: 51.9%
- `gov_subsidy_rd`: 40.8%

### provincial_panel_full.csv
- 行数: 434, 列数: 17
- 省份数: 31

## 二、新 CSMAR 数据表 (8个)

### STK_LISTEDCOINFOANL.xlsx
- 来源: 上市公司基本信息年度表093147121(仅供中央财经大学使用)
- 总行数: 71,847, 列数: 41
- 年份范围: 2000 – 2025
- 2019-2024 行数: 29,172
- 列名: ['Symbol', 'ShortName', 'EndDate', 'ListedCoID', 'SecurityID', 'IndustryName', 'IndustryCode', 'IndustryNameC', 'IndustryCodeC', 'IndustryNameD', 'IndustryCodeD', 'RegisterAddress', 'OfficeAddress', 'Zipcode', 'Secretary', 'SecretaryTel', 'SecretaryFax', 'SecretaryEmail', 'SecurityConsultant', 'SocialCreditCode', 'Sigchange', 'Lng', 'Lat', 'ISIN', 'FullName', 'LegalRepresentative', 'EstablishDate', 'Crcd', 'RegisterCapital', 'Website', 'BusinessScope', 'RegisterLongitude', 'RegisterLatitude', 'EMAIL', 'LISTINGDATE', 'PROVINCECODE', 'PROVINCE', 'CITYCODE', 'CITY', 'MAINBUSSINESS', 'LISTINGSTATE']

### HLD_Contrshr.xlsx
- 来源: 上市公司控制人文件191519199(仅供中央财经大学使用)
- 总行数: 117,943, 列数: 15
- 年份范围: 2016 – 2025
- 2019-2024 行数: 81,571
- 列名: ['Stkcd', 'Reptdt', 'S0701a', 'S0702a', 'S0701b', 'S0703a', 'S0704a', 'S0705a', 'S0702b', 'S0703b', 'S0706b', 'Notes', 'S0704b', 'S0704c', 'Seperation']

### FS_Comins.xlsx
- 来源: 利润表185758185(仅供中央财经大学使用)
- 总行数: 383,828, 列数: 7
- 年份范围: 2016 – 2025
- 2019-2024 行数: 257,762
- 列名: ['Stkcd', 'ShortName', 'Accper', 'Typrep', 'B001101000', 'B001000000', 'B002100000']

### PT_LCDOMFORAPPLY.xlsx
- 来源: 国内外专利申请获得情况表191134530(仅供中央财经大学使用)
- 总行数: 55,145, 列数: 11
- 年份范围: 2016 – 2025
- 2019-2024 行数: 42,555
- 列名: ['Symbol', 'EndDate', 'StateTypeCode', 'Area', 'ApplyTypeCode', 'ApplyType', 'Source', 'Patents', 'Invention', 'UtilityModel', 'Design']

### FN_FN056.xlsx
- 来源: 政府补助191747287(仅供中央财经大学使用)
- 总行数: 765,169, 列数: 11
- 年份范围: 2016 – 2025
- 2019-2024 行数: 532,984
- 列名: ['Stkcd', 'ShortName', 'Accper', 'DataSources', 'Typrep', 'Fn05601', 'Fn05602', 'Fn05603', 'Fn05606', 'Fn05604', 'Fnother']

### FS_Comscfd.xlsx
- 来源: 现金流量表(直接法)190813693(仅供中央财经大学使用)
- 总行数: 383,801, 列数: 6
- 年份范围: 2016 – 2025
- 2019-2024 行数: 257,743
- 列名: ['Stkcd', 'ShortName', 'Accper', 'Typrep', 'C001100000', 'C001200000']

### PT_LCRDSPENDING.xlsx
- 来源: 研发投入情况表191351698(仅供中央财经大学使用)
- 总行数: 48,164, 列数: 14
- 年份范围: 2016 – 2025
- 2019-2024 行数: 31,206
- 列名: ['Symbol', 'EndDate', 'Source', 'StateTypeCode', 'RDPerson', 'RDPersonRatio', 'RDSpendSum', 'RDSpendSumRatio', 'RDExpenses', 'RDInvest', 'RDInvestRatio', 'RDInvestNetprofitRatio', 'Currency', 'Explanation']

### FS_Combas.xlsx
- 来源: 资产负债表190452346(仅供中央财经大学使用)
- 总行数: 383,825, 列数: 5
- 年份范围: 2016 – 2025
- 2019-2024 行数: 257,753
- 列名: ['Stkcd', 'ShortName', 'Accper', 'Typrep', 'A001000000']

## 三、关键变量详解

### 3.1 专利表 (PT_LCDOMFORAPPLY)
- 2019-2024 总行数: 42,555

**ApplyType 分布:**
- 截至报告期末累计获得: 12,978
- 已授权: 7,692
- 已申请: 6,908
- 已获得: 5,816
- 截止报告期末累计已授权: 5,107
- 截止报告期末累计已被受理: 4,054

**Area 分布 (1=国内, 2=国外):**
- 国内: 38,700
- 国外: 3,855

**Invention (发明专利) 按 ApplyType 描述统计:**
              count  unique  top  freq
ApplyType                             
已授权            5454     305    1   568
已申请            5071     422    2   223
已获得            4707     233    1   471
截止报告期末累计已授权    3608     559    2    71
截止报告期末累计已被受理   3098     860   32    25
截至报告期末累计获得    10232     715    2   231

### 3.2 研发投入表 (PT_LCRDSPENDING)
- 2019-2024 总行数: 31,206

| 变量 | 非缺失数 | 缺失率 | 均值 | 中位数 |
|------|----------|--------|------|--------|
| RDPerson | 28,491 | 8.7% | 6.1e+02 | 2e+02 |
| RDPersonRatio | 28,278 | 9.4% | 18 | 14 |
| RDSpendSum | 31,050 | 0.5% | 2.9e+08 | 6.2e+07 |
| RDSpendSumRatio | 30,420 | 2.5% | 28 | 4.4 |
| RDExpenses | 12,256 | 60.7% | 3.6e+08 | 6.9e+07 |
| RDInvest | 21,321 | 31.7% | 3.4e+07 | 0 |

### 3.3 利润表 (FS_Comins)
- 2019-2024 合并报表(A): 145,492 行
- 2019-2024 母公司报表(B): 112,270 行

**合并报表 变量统计:**

| 代码 | 含义 | 非缺失 | 缺失率 | 均值 |
|------|------|--------|--------|------|
| B001101000 | 营业收入 | 142,603 | 2.0% | 7.9e+09 |
| B001000000 | 利润总额 | 145,492 | 0.0% | 9.5e+08 |
| B002100000 | 减:所得税费用 | 143,558 | 1.3% | 1.8e+08 |

### 3.4 控制人表 (HLD_Contrshr)
- 2019-2024 总行数: 81,571

**S0702b (实际控制人性质) 分布:**

- 3110: 52,337
- 2120: 9,555
- 2100: 2,961
- 1100: 2,921
- 3120: 2,033
- 3110,3110: 1,907
- 3200: 1,697
- 3110,3110,3110: 730
- 2000: 475
- 3000: 325
- 3110,3110,3110,3110: 302
- 1000: 274
- 1210: 202
- 3110,1000: 182
- 2500: 177
- 3110,3110,1000: 154
- 1230: 149
- 3110,3200: 147
- 3110,3110,3110,3110,3110: 120
- 1200: 110

### 3.5 基本信息表 (STK_LISTEDCOINFOANL)
- 2019-2024 总行数: 29,172

**PROVINCE 非缺失:** 29,172 / 29,172 (100.0%)

**省份分布 (Top 15):**
- 广东省: 4,755
- 浙江省: 3,756
- 江苏省: 3,630
- 北京市: 2,595
- 上海市: 2,383
- 山东省: 1,669
- 福建省: 984
- 四川省: 968
- 安徽省: 932
- 湖北省: 811
- 湖南省: 793
- 河南省: 625
- 辽宁省: 499
- 河北省: 435
- 江西省: 430

### 3.6 政府补助表 (FN_FN056)
- 2019-2024 明细行数: 532,984

**DataSources (列报会计科目) 分布:**
- 1: 476,340
- 2: 42,209
- 4: 6,101
- 5: 4,516
- 11: 732
- 14: 606
- 23: 363
- 1,2: 294
- 22: 286
- 8: 262

**研发相关项目:** 115,468 / 532,984 (21.7%)
- 研发相关补助金额: sum=1.1e+11, mean=1.1e+06

**按 stock_code×year 汇总 (合并报表 Typrep=1):**
- 企业-年数: 26,621
- total_subsidy: mean=1e+08, median=3e+07
- 有研发补助的企业-年: 17,347
- rd_subsidy: mean=6.5e+06, median=1.9e+06

### 3.7 资产负债表 (FS_Combas)
- 2019-2024 合并报表: 145,484 行
- 资产总计: n=145,483, miss=0.0%, mean=7.3e+10, median=3.7e+09

### 3.8 现金流量表 (FS_Comscfd)
- 2019-2024 合并报表: 145,481 行
- C001100000: n=145,481, miss=0.0%, mean=1.4e+10
- C001200000: n=145,481, miss=0.0%, mean=1.3e+10

## 四、跨表匹配率 (与现有 firm_panel 的 stock_code × year)

现有 firm_panel 企业-年: 4,033

| 数据表 | 企业-年对 | 匹配数 | 匹配率 |
|--------|----------|--------|--------|
| 专利表 (PT_LCDOMFORAPPLY) | 18,274 | 4,033 | 100.0% |
| 研发投入表 (PT_LCRDSPENDING) | 30,130 | 4,033 | 100.0% |
| 利润表-合并 (FS_Comins, A) | 30,159 | 4,033 | 100.0% |
| 控制人表 (HLD_Contrshr) | 28,814 | 4,033 | 100.0% |
| 基本信息表 (STK_LISTEDCOINFOANL) | 29,172 | 4,033 | 100.0% |
| 资产负债表-合并 (FS_Combas, A) | 30,157 | 4,033 | 100.0% |
| 政府补助表 (FN_FN056) | 26,623 | 3,888 | 96.4% |
| 现金流量表-合并 (FS_Comscfd, A) | 30,157 | 4,033 | 100.0% |

## 五、12条优先级数据缺口对照

| 优先级 | 需求 | 数据源 | 状态 | 备注 |
|--------|------|--------|------|------|
| P1 | 企业注册地省份 | `STK_LISTEDCOINFOANL.PROVINCE` | [已解决] | 省份字段全覆盖, >99%非缺失 |
| P2 | 当年发明专利申请数 | `PT_LCDOMFORAPPLY.Invention (ApplyType=已申请)` | [已解决] | 可构造 firm_invention_apply |
| P3 | 当年发明专利授权数 | `PT_LCDOMFORAPPLY.Invention (ApplyType=已授权)` | [已解决] | 可构造 firm_invention_grant |
| P4 | 真实研发费用 | `PT_LCRDSPENDING.RDSpendSum` | [已解决] | 年报披露真实研发投入, 替代 rd_expense_est |
| P5 | 研发加计扣除享受额 | `PT_LCRDSPENDING.RDSpendSum * rd_deduction_rate` | [可构造] | 无直接字段, 用研发投入*政策比例估算 |
| P6 | 2017-2018年面板 | `所有8个新表` | [已解决] | 年份均从2016起, 政策前窗口扩充至6年 |
| P7 | 营业收入 | `FS_Comins.B001101000` | [已解决] | 合并报表全覆盖 |
| P8 | 所得税费用 | `FS_Comins.B002100000` | [已解决] | 合并报表全覆盖 |
| P9 | 利润总额 | `FS_Comins.B001000000` | [已解决] | 合并报表全覆盖 |
| P10 | 所有制性质 | `HLD_Contrshr.S0702b` | [已解决] | 实际控制人性质, 可构造SOE |
| P11 | 研发人员数量 | `PT_LCRDSPENDING.RDPerson` | [已解决] | + RDPersonRatio 占比 |
| P12 | 研发政府补助 | `FN_FN056.Fn05601 + Fn05602` | [已解决] | 从76万明细中筛选研发相关, 汇总到企业-年 |

## 六、建模修改建议

### 6.1 因变量升级

当前 `patent_stock` (累计专利存量) → 建议替换/补充:
- **主因变量:** `firm_invention_apply` (当年发明专利申请数) — 流量型高质量创新指标
- **替代因变量:** `firm_invention_grant` (当年发明专利授权数) — 高质量创新结果
- **保留:** `patent_stock` 作为稳健性对照

### 6.2 核心自变量替换

当前 `rd_expense_est` (由加计扣除反推) → 替换为:
- `RDSpendSum` — 年报披露的真实研发投入金额
- `RDSpendSumRatio` — 研发投入占营业收入比例 (直接取自 CSMAR)
- 可重新计算: `rd_intensity = RDSpendSum / B001101000 * 100`

当前 `rd_tax_deduction` (99.8%为负) → 替换为:
- 构造: `rd_tax_deduction_est = RDSpendSum × rd_deduction_rate × 0.25`
- 注意区分行业: 制造业 2021年前75%, 2021年起100%; 一般企业不同

### 6.3 新增变量

| 新变量 | 来源 | 用途 |
|--------|------|------|
| `soe` | HLD_Contrshr.S0702b | 国企/民企异质性 |
| `rd_staff` | PT_LCRDSPENDING.RDPerson | 人力投入机制检验 |
| `revenue` | FS_Comins.B001101000 | 计算标准研发强度 |
| `profit_before_tax` | FS_Comins.B001000000 | 计算 ETR |
| `income_tax_expense` | FS_Comins.B002100000 | 计算 ETR |
| `total_assets` | FS_Combas.A001000000 | 替代 ln_assets |
| `rd_subsidy` | FN_FN056 (研发项目汇总) | 补贴机制检验 |
| `invention_apply` | PT_LCDOMFORAPPLY (已申请) | 主因变量 |
| `invention_grant` | PT_LCDOMFORAPPLY (已授权) | 稳健性因变量 |

### 6.4 样本时间扩展

- 当前: 2019-2024 (6年, 仅2个政策前年份)
- 建议: 2017-2024 (8年, 4个政策前年份) 或 2016-2024 (9年)
- 所有新表年份从2016起, 扩展无损

### 6.5 省份匹配修复

- 当前 provnice_std 覆盖率 48%, 因为依赖 `实证数据.xlsx` sheet 4
- 用 STK_LISTEDCOINFOANL.PROVINCE 重新匹配, 预计覆盖率 >99%

---
报告生成时间: 2026-05-16 20:21:15
