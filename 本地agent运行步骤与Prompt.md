# 本地 agent 实际运行试验步骤与输出 Prompt

## 一、建模口径

根据《最终数据清单.md》，当前数据适合围绕 2021 年制造业研发费用加计扣除比例提高政策进行准政策评估。处理组是制造业企业，时间冲击是 2021 年后，核心变量是：

```text
manufacturing_post2021 = manufacturing × post2021
```

主模型不把结论写成严格因果识别，而写成“企业固定效应和年份固定效应控制下，制造业政策冲击与企业创新产出变化之间的关系”。原因是当前主样本为 2019-2024 年，政策前只有 2019、2020 两个年份，平行趋势检验信息不足。

## 二、本地目录结构

在本地新建项目目录，例如：

```bash
mkdir tech_policy_model
cd tech_policy_model
mkdir data outputs code docs
```

把数据文件放入 `data/`：

```text
data/firm_panel_final.xlsx          # 主分析数据，必须
data/provincial_panel_full.csv      # 省级面板，可选；若主表已经合并省级变量，则可不放
docs/最终数据清单.md                # 数据清单，用于审计说明
code/run_final_policy_models.py     # 建模脚本
```

## 三、安装环境

建议使用 Python 3.10 或 3.11。

```bash
python -m venv .venv
```

macOS / Linux：

```bash
source .venv/bin/activate
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

安装依赖：

```bash
pip install pandas numpy scipy statsmodels linearmodels openpyxl
```

`linearmodels` 用于双向固定效应面板模型。如果安装失败，脚本会自动退回到 `statsmodels` 的企业和年份虚拟变量固定效应模型。

## 四、运行命令

推荐运行：

```bash
python code/run_final_policy_models.py \
  --data data/firm_panel_final.xlsx \
  --province data/provincial_panel_full.csv \
  --out outputs
```

如果主表已经包含省级变量，可以省略省级文件：

```bash
python code/run_final_policy_models.py \
  --data data/firm_panel_final.xlsx \
  --out outputs
```

## 五、模型设计

### 1. 基准 DID 模型

```text
ln_patent_stock_it = β manufacturing_post2021_it
                   + γ Controls_it
                   + FirmFE_i + YearFE_t + ε_it
```

其中：

```text
Controls = rd_intensity, ln_assets, roa, lev, firm_age, dual_position
```

解释：β 衡量 2021 年后制造业企业相对于非制造业企业的专利存量变化差异。

### 2. 税收优惠强度模型

```text
ln_patent_stock_it = β manufacturing_post2021_it
                   + θ ln_rd_tax_deduction_it
                   + γ Controls_it
                   + FirmFE_i + YearFE_t + ε_it
```

注意：`ln_rd_tax_deduction` 属于政策强度或政策享受变量，但可能存在反向因果和同步性，不能单独解释为因果效应。

### 3. 滞后一期税收优惠模型

```text
ln_patent_stock_it = β manufacturing_post2021_it
                   + θ ln_rd_tax_deduction_i,t-1
                   + γ Controls_it
                   + FirmFE_i + YearFE_t + ε_it
```

用于缓解同步性问题，但不能完全解决内生性。

### 4. 创新投入机制检验

```text
rd_intensity_it = β manufacturing_post2021_it
                + γ Controls_without_rd_it
                + FirmFE_i + YearFE_t + ε_it
```

若 β 显著为正，说明政策可能通过提高研发投入强度影响创新产出。

### 5. 补贴机制检验

```text
ln_patent_stock_it = β manufacturing_post2021_it
                   + θ ln_gov_subsidy_rd_it
                   + γ Controls_it
                   + FirmFE_i + YearFE_t + ε_it
```

因为 `gov_subsidy_rd` 覆盖率约 59%，脚本会同时构造：

```text
gov_subsidy_rd_zero
gov_subsidy_rd_missing
ln_gov_subsidy_rd
```

防止简单删样本导致偏误。

### 6. 地方财政科技支出交互模型

```text
ln_patent_stock_it = β manufacturing_post2021_it
                   + θ manufacturing_post2021_it × sci_tech_exp_ratio_pt
                   + γ Controls_it
                   + FirmFE_i + YearFE_t + ε_it
```

该模型只适用于省份匹配成功的子样本。若省份覆盖率仍为 48%，结论必须写成子样本结果。

### 7. 事件研究

以 2020 年为基准年，构造：

```text
event_m2 = manufacturing × 1[year = 2019]
event_p0 = manufacturing × 1[year = 2021]
event_p1 = manufacturing × 1[year = 2022]
event_p2 = manufacturing × 1[year = 2023]
event_p3 = manufacturing × 1[year = 2024]
```

如果 `event_m2` 显著，说明政策前趋势存在差异。由于只有一个政策前年份系数，该检验只能作为弱平行趋势检查。

## 六、脚本输出文件

运行成功后，`outputs/` 应包含：

```text
00_data_audit.json                         # 数据审计，字段缺失、样本、年份、警告
00_missing_rates.csv                       # 各字段缺失率
01_descriptive_statistics.csv              # 描述性统计
01_sample_distribution_year_treat.csv      # 年份 × 处理组样本分布
02_baseline_results.csv                    # 基准模型结果
03_mechanism_results.csv                   # 机制检验结果
04_robustness_results.csv                  # 稳健性结果
05_event_study_results.csv                 # 事件研究结果
06_validity_checks.md                      # 效度检验说明
07_full_model_summaries.txt                # 完整回归输出
clean_panel_for_models.csv                 # 清洗后建模数据
```

## 七、本地 agent 执行 Prompt

把下面这一段完整发给本地 agent，例如 Claude Code、Cursor Agent、OpenAI Codex CLI 或其他能操作本地文件的 agent。

```text
你是一个严谨的计量经济学与政策研究助理。请在当前项目目录中完成“科技自主创新政策实证研究”的本地建模实验。

任务背景：
我有一个企业年度面板数据 data/firm_panel_final.xlsx，来自《最终数据清单.md》。样本为中国上市公司，年份为2019-2024。研究对象是科技自主创新政策，核心政策冲击为2021年制造业企业研发费用加计扣除比例提高至100%。处理组为 manufacturing=1 的制造业企业，对照组为非制造业企业。核心交互项是 manufacturing_post2021。

你必须遵守以下原则：
1. 不得补造数据。
2. 缺少字段时，在输出中列明缺失字段，并跳过依赖该字段的模型。
3. 不得把估算变量 rd_expense_est 写成真实研发费用。
4. 不得把累计专利 patent_stock 解释为当年新增专利。
5. 当前数据只有2019-2024年，因此只能做有限的政策前趋势检查，不能夸大为严格因果识别。
6. 所有回归必须至少控制企业固定效应和年份固定效应，标准误按企业聚类。

请按以下步骤执行：

第一步，检查目录结构。确认以下文件是否存在：
- data/firm_panel_final.xlsx
- data/provincial_panel_full.csv，若不存在则继续运行主表模型
- docs/最终数据清单.md，若不存在则不影响建模
- code/run_final_policy_models.py

第二步，创建或激活 Python 环境，并安装依赖：
pandas, numpy, scipy, statsmodels, linearmodels, openpyxl。

第三步，运行：
python code/run_final_policy_models.py --data data/firm_panel_final.xlsx --province data/provincial_panel_full.csv --out outputs
如果 provincial_panel_full.csv 不存在，则运行：
python code/run_final_policy_models.py --data data/firm_panel_final.xlsx --out outputs

第四步，检查 outputs 目录中是否生成以下文件：
- 00_data_audit.json
- 01_descriptive_statistics.csv
- 02_baseline_results.csv
- 03_mechanism_results.csv
- 04_robustness_results.csv
- 05_event_study_results.csv
- 06_validity_checks.md
- 07_full_model_summaries.txt

第五步，读取结果并输出一份中文实验报告。报告必须包括：
1. 数据审计结论：样本量、企业数、年份范围、字段缺失、缺失率较高变量。
2. 基准DID结果：重点解释 manufacturing_post2021 的系数、标准误、p值和方向。
3. 税收优惠强度结果：解释 ln_rd_tax_deduction 的相关性，但提醒不能直接解释为因果。
4. 机制检验：说明 rd_intensity 与 gov_subsidy_rd 的结果是否支持机制。
5. 地方财政科技支出交互：如果 sci_tech_exp_ratio 可用，说明交互项结果；如果不可用，说明未能检验。
6. 稳健性分析：比较 post2022、asinh因变量、剔除2024后的核心结果是否一致。
7. 效度检验：说明事件研究和平行趋势证据是否充分。注意，2019-2020只有两个政策前年份，因此不得写成充分通过平行趋势检验。
8. 结论：用谨慎措辞说明科技自主创新政策、税收优惠、财政补贴、地方财政科技支出与企业创新之间的关系。
9. 数据不足：列出仍需补充的数据，例如 revenue、total_assets 原值、income_tax_expense、profit_before_tax、soe、rd_staff、当年发明专利申请和授权等。
10. 文件清单：列出本次生成的所有输出文件。

输出要求：
- 用中文。
- 不要编造系数、显著性或样本量。必须从 outputs 中读取。
- 如果某个模型没有成功运行，要说明原因。
- 给出可直接写入论文的“实证结果小结”和“政策解释小结”。
- 最后给出“还需要补充的数据清单”。
```

## 八、本地 agent 最终输出 Prompt 模板

当 agent 已经跑完模型后，让它用下面的模板生成最终报告：

```text
请根据 outputs/00_data_audit.json、outputs/02_baseline_results.csv、outputs/03_mechanism_results.csv、outputs/04_robustness_results.csv、outputs/05_event_study_results.csv、outputs/06_validity_checks.md 和 outputs/07_full_model_summaries.txt，生成一份中文实证结果报告。

报告结构如下：

一、数据与样本说明
说明样本量、企业数、年份范围、处理组和对照组设置、主要变量定义、缺失情况。

二、模型设定
写出基准DID模型、机制检验模型、地方财政科技支出交互模型、稳健性模型。说明企业固定效应、年份固定效应和企业聚类标准误。

三、基准回归结果
读取 manufacturing_post2021 的系数、标准误、p值、样本量。解释方向和显著性。不得编造。

四、机制检验结果
说明研发投入强度、研发相关政府补助是否构成机制支持。若结果不显著，要明确写不显著。

五、地方财政科技支出与制度环境
如果存在 did_x_sci_ratio 或 sci_tech_exp_ratio 结果，解释地方财政科技支出强度是否强化政策效果。如果模型未运行，说明是因为省份或省级变量覆盖不足。

六、稳健性与效度检验
比较替代政策年份、替代因变量、剔除2024样本、事件研究。重点说明平行趋势检验受限于政策前样本不足。

七、研究结论
用谨慎语言总结：政策冲击是否与企业专利存量增长、研发投入强度、税收优惠强度、财政补贴存在统计关系。不得扩大为未经证实的因果结论。

八、政策研究解释
结合财政科技支出、税收优惠、研发补贴、政府采购等政策工具，解释政策作用机制：降低研发成本、缓解融资约束、稳定企业预期、强化地方创新环境。必须区分理论解释和实证结果。

九、数据局限与补充清单
列出 revenue、total_assets、income_tax_expense、profit_before_tax、soe、rd_staff、企业当年发明专利申请数和授权数、政府采购合同金额、科技型中小企业和高新技术企业资格等仍需补充数据。

十、可写入论文的结论段
生成一段400-600字的正式论文语言结论。
```
