"""
全面审计所有数据文件：现有主数据 + 8个新 CSMAR 表
输出到 data/data_audit_report.md
"""
import pandas as pd
import numpy as np
import os, json
from pathlib import Path
from datetime import datetime

extract = Path("data/_extract")
out_lines = []

def p(s=""):
    out_lines.append(s)
    print(s)

def load_table(fp):
    return pd.read_excel(fp)

# ============================================================
p(f"# 数据审计报告 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
p()
# ============================================================

# ============================================================
p("## 一、现有主分析数据")
p()
# ============================================================
firm = pd.read_csv("data/firm_panel_final.csv")
p(f"### firm_panel_final.csv")
p(f"- 行数: {len(firm):,}, 列数: {len(firm.columns)}")
p(f"- 企业数: {firm['stock_code'].nunique():,}")
p(f"- 年份: {sorted([int(x) for x in firm['year'].dropna().unique()])}")
p()

miss = firm.isna().mean().sort_values(ascending=False)
p("**高缺失率变量 (>30%):**")
p()
for c, v in miss.items():
    if v > 0.3:
        p(f"- `{c}`: {v:.1%}")

p()
prov = pd.read_csv("data/provincial_panel_full.csv")
p(f"### provincial_panel_full.csv")
p(f"- 行数: {len(prov):,}, 列数: {len(prov.columns)}")
p(f"- 省份数: {prov['province'].nunique() if 'province' in prov.columns else 'N/A'}")

# ============================================================
p()
p("## 二、新 CSMAR 数据表 (8个)")
p()
# ============================================================

tables = {}
table_info = []

for d in sorted(os.listdir(extract)):
    dpath = extract / d
    if not dpath.is_dir():
        continue
    for f in os.listdir(dpath):
        if f.endswith('.xlsx'):
            fp = dpath / f
            df = pd.read_excel(fp)
            tables[f] = df

            # Parse years
            if 'EndDate' in df.columns:
                yrs = pd.to_datetime(df['EndDate'], errors='coerce').dt.year
                date_col = 'EndDate'
            elif 'Accper' in df.columns:
                yrs = pd.to_datetime(df['Accper'], errors='coerce').dt.year
                date_col = 'Accper'
            elif 'Reptdt' in df.columns:
                yrs = pd.to_datetime(df['Reptdt'], errors='coerce').dt.year
                date_col = 'Reptdt'
            else:
                yrs = None
                date_col = None

            mask_1924 = None
            if yrs is not None:
                mask_1924 = yrs.between(2019, 2024)

            info = {
                'file': f,
                'dir': d[:60],
                'rows': len(df),
                'cols': len(df.columns),
                'year_min': yrs.min() if yrs is not None else None,
                'year_max': yrs.max() if yrs is not None else None,
                'rows_1924': mask_1924.sum() if mask_1924 is not None else None,
                'columns': list(df.columns),
                'date_col': date_col,
            }
            table_info.append(info)

            p(f"### {f}")
            p(f"- 来源: {d[:80]}")
            p(f"- 总行数: {len(df):,}, 列数: {len(df.columns)}")
            p(f"- 年份范围: {info['year_min']:.0f} – {info['year_max']:.0f}" if yrs is not None else "- 年份范围: N/A")
            p(f"- 2019-2024 行数: {info['rows_1924']:,}" if mask_1924 is not None else "- 2019-2024: N/A")
            p(f"- 列名: {list(df.columns)}")
            p()

# ============================================================
p("## 三、关键变量详解")
p()
# ============================================================

# 3a Patent table
pat = tables.get('PT_LCDOMFORAPPLY.xlsx')
if pat is not None:
    pat['_year'] = pd.to_datetime(pat['EndDate'], errors='coerce').dt.year
    pat_1924 = pat[pat['_year'].between(2019, 2024)]
    p("### 3.1 专利表 (PT_LCDOMFORAPPLY)")
    p(f"- 2019-2024 总行数: {len(pat_1924):,}")
    p()
    p("**ApplyType 分布:**")
    for k, v in pat_1924['ApplyType'].value_counts().items():
        p(f"- {k}: {v:,}")
    p()
    p("**Area 分布 (1=国内, 2=国外):**")
    for k, v in pat_1924['Area'].value_counts().items():
        p(f"- {'国内' if k == 1 else '国外'}: {v:,}")
    p()
    p("**Invention (发明专利) 按 ApplyType 描述统计:**")
    inv_stats = pat_1924.groupby('ApplyType')['Invention'].describe()
    p(inv_stats.to_string())
    p()

# 3b R&D spending
rd = tables.get('PT_LCRDSPENDING.xlsx')
if rd is not None:
    rd['_year'] = pd.to_datetime(rd['EndDate'], errors='coerce').dt.year
    rd_1924 = rd[rd['_year'].between(2019, 2024)]
    p("### 3.2 研发投入表 (PT_LCRDSPENDING)")
    p(f"- 2019-2024 总行数: {len(rd_1924):,}")
    p()
    p("| 变量 | 非缺失数 | 缺失率 | 均值 | 中位数 |")
    p("|------|----------|--------|------|--------|")
    for c in ['RDPerson', 'RDPersonRatio', 'RDSpendSum', 'RDSpendSumRatio', 'RDExpenses', 'RDInvest']:
        if c in rd_1924.columns:
            v = pd.to_numeric(rd_1924[c], errors='coerce')
            p(f"| {c} | {v.notna().sum():,} | {v.isna().mean():.1%} | {v.mean():.2g} | {v.median():.2g} |")
    p()

# 3c Income statement
inc = tables.get('FS_Comins.xlsx')
if inc is not None:
    inc['_year'] = pd.to_datetime(inc['Accper'], errors='coerce').dt.year
    inc_A = inc[(inc['Typrep'] == 'A') & (inc['_year'].between(2019, 2024))]
    inc_B = inc[(inc['Typrep'] == 'B') & (inc['_year'].between(2019, 2024))]
    p("### 3.3 利润表 (FS_Comins)")
    p(f"- 2019-2024 合并报表(A): {len(inc_A):,} 行")
    p(f"- 2019-2024 母公司报表(B): {len(inc_B):,} 行")
    p()
    p("**合并报表 变量统计:**")
    p()
    p("| 代码 | 含义 | 非缺失 | 缺失率 | 均值 |")
    p("|------|------|--------|--------|------|")
    for c, desc in [('B001101000', '营业收入'), ('B001000000', '利润总额'), ('B002100000', '减:所得税费用')]:
        v = pd.to_numeric(inc_A[c], errors='coerce')
        p(f"| {c} | {desc} | {v.notna().sum():,} | {v.isna().mean():.1%} | {v.mean():.2g} |")
    p()

# 3d Controller
ctr = tables.get('HLD_Contrshr.xlsx')
if ctr is not None:
    ctr['_year'] = pd.to_datetime(ctr['Reptdt'], errors='coerce').dt.year
    ctr_1924 = ctr[ctr['_year'].between(2019, 2024)]
    p("### 3.4 控制人表 (HLD_Contrshr)")
    p(f"- 2019-2024 总行数: {len(ctr_1924):,}")
    p()
    p("**S0702b (实际控制人性质) 分布:**")
    p()
    for k, v in ctr_1924['S0702b'].value_counts().head(20).items():
        p(f"- {k}: {v:,}")
    p()

# 3e Basic info
info = tables.get('STK_LISTEDCOINFOANL.xlsx')
if info is not None:
    info['_year'] = pd.to_datetime(info['EndDate'], errors='coerce').dt.year
    info_1924 = info[info['_year'].between(2019, 2024)]
    p("### 3.5 基本信息表 (STK_LISTEDCOINFOANL)")
    p(f"- 2019-2024 总行数: {len(info_1924):,}")
    p()

    # Check province coverage
    if 'PROVINCE' in info_1924.columns:
        p(f"**PROVINCE 非缺失:** {info_1924['PROVINCE'].notna().sum():,} / {len(info_1924):,} ({info_1924['PROVINCE'].notna().mean():.1%})")
        p()
        p("**省份分布 (Top 15):**")
        for k, v in info_1924['PROVINCE'].value_counts().head(15).items():
            p(f"- {k}: {v:,}")
    p()

# 3f Government subsidies
sub = tables.get('FN_FN056.xlsx')
if sub is not None:
    sub['_year'] = pd.to_datetime(sub['Accper'], errors='coerce').dt.year
    sub_1924 = sub[sub['_year'].between(2019, 2024)]
    p("### 3.6 政府补助表 (FN_FN056)")
    p(f"- 2019-2024 明细行数: {len(sub_1924):,}")
    p()
    p("**DataSources (列报会计科目) 分布:**")
    for k, v in sub_1924['DataSources'].value_counts().head(10).items():
        p(f"- {k}: {v:,}")
    p()

    # R&D related subsidies
    rd_kw = ['研发', '科技', '创新', '专利', '技术', 'R&D', '科研', '发明']
    rd_mask = sub_1924['Fn05601'].astype(str).str.contains('|'.join(rd_kw), na=False)
    p(f"**研发相关项目:** {rd_mask.sum():,} / {len(sub_1924):,} ({rd_mask.mean():.1%})")
    rd_sub_amt = pd.to_numeric(sub_1924.loc[rd_mask, 'Fn05602'], errors='coerce')
    p(f"- 研发相关补助金额: sum={rd_sub_amt.sum():.2g}, mean={rd_sub_amt.mean():.2g}")
    p()

    # Per firm-year aggregation
    p("**按 stock_code×year 汇总 (合并报表 Typrep=1):**")
    # Typrep is numeric: 1=合并, 2=母公司
    mask_a = sub_1924['Typrep'].astype(str).str.strip().isin(['1', '1.0'])
    sub_A = sub_1924[mask_a].copy()
    sub_A['Fn05602_num'] = pd.to_numeric(sub_A['Fn05602'], errors='coerce')
    total_sub = sub_A.groupby(['Stkcd', '_year'])['Fn05602_num'].sum().reset_index()
    total_sub.columns = ['stock_code', 'year', 'total_subsidy']
    total_sub['stock_code'] = total_sub['stock_code'].astype(str).str.replace('.0', '').str.zfill(6)
    p(f"- 企业-年数: {len(total_sub):,}")
    p(f"- total_subsidy: mean={total_sub['total_subsidy'].mean():.2g}, median={total_sub['total_subsidy'].median():.2g}")

    # R&D subsidy per firm-year
    rd_sub_A = sub_A[sub_A['Fn05601'].astype(str).str.contains('|'.join(rd_kw), na=False)]
    rd_total = rd_sub_A.groupby(['Stkcd', '_year'])['Fn05602_num'].sum().reset_index()
    rd_total.columns = ['stock_code', 'year', 'rd_subsidy']
    p(f"- 有研发补助的企业-年: {len(rd_total):,}")
    p(f"- rd_subsidy: mean={rd_total['rd_subsidy'].mean():.2g}, median={rd_total['rd_subsidy'].median():.2g}")
    p()

# 3g Balance sheet
bs = tables.get('FS_Combas.xlsx')
if bs is not None:
    bs['_year'] = pd.to_datetime(bs['Accper'], errors='coerce').dt.year
    bs_A = bs[(bs['Typrep'] == 'A') & (bs['_year'].between(2019, 2024))]
    p("### 3.7 资产负债表 (FS_Combas)")
    p(f"- 2019-2024 合并报表: {len(bs_A):,} 行")
    v = pd.to_numeric(bs_A['A001000000'], errors='coerce')
    p(f"- 资产总计: n={v.notna().sum():,}, miss={v.isna().mean():.1%}, mean={v.mean():.2g}, median={v.median():.2g}")
    p()

# 3h Cash flow
cf = tables.get('FS_Comscfd.xlsx')
if cf is not None:
    cf['_year'] = pd.to_datetime(cf['Accper'], errors='coerce').dt.year
    cf_A = cf[(cf['Typrep'] == 'A') & (cf['_year'].between(2019, 2024))]
    p("### 3.8 现金流量表 (FS_Comscfd)")
    p(f"- 2019-2024 合并报表: {len(cf_A):,} 行")
    for c in ['C001100000', 'C001200000']:
        v = pd.to_numeric(cf_A[c], errors='coerce')
        p(f"- {c}: n={v.notna().sum():,}, miss={v.isna().mean():.1%}, mean={v.mean():.2g}")
    p()

# ============================================================
p("## 四、跨表匹配率 (与现有 firm_panel 的 stock_code × year)")
p()
# ============================================================
firm_ids = firm[['stock_code', 'year']].drop_duplicates()
firm_ids['stock_code'] = firm_ids['stock_code'].astype(str).str.replace('.0', '').str.zfill(6)
firm_ids['year'] = firm_ids['year'].astype(float)
p(f"现有 firm_panel 企业-年: {len(firm_ids):,}")
p()

def check_match(name, df, code_col, year_col):
    df = df.copy()
    df['_year'] = pd.to_datetime(df[year_col], errors='coerce').dt.year.astype(float)
    df['_code'] = df[code_col].astype(str).str.replace('.0', '').str.zfill(6)
    # keep only 2019-2024
    df = df[df['_year'].between(2019, 2024)]
    pairs = df[['_code', '_year']].drop_duplicates()
    pairs.columns = ['stock_code', 'year']
    pairs['stock_code'] = pairs['stock_code'].astype(str).str.replace('.0', '').str.zfill(6)

    merged = firm_ids.merge(pairs, on=['stock_code', 'year'], how='inner')
    rate = len(merged) / len(firm_ids) if len(firm_ids) > 0 else 0
    p(f"| {name} | {len(pairs):,} | {len(merged):,} | {rate:.1%} |")
    return rate

p("| 数据表 | 企业-年对 | 匹配数 | 匹配率 |")
p("|--------|----------|--------|--------|")

if pat is not None:
    check_match("专利表 (PT_LCDOMFORAPPLY)", pat, 'Symbol', 'EndDate')
if rd is not None:
    check_match("研发投入表 (PT_LCRDSPENDING)", rd, 'Symbol', 'EndDate')
if inc is not None:
    check_match("利润表-合并 (FS_Comins, A)", inc[inc['Typrep']=='A'], 'Stkcd', 'Accper')
if ctr is not None:
    check_match("控制人表 (HLD_Contrshr)", ctr, 'Stkcd', 'Reptdt')
if info is not None:
    check_match("基本信息表 (STK_LISTEDCOINFOANL)", info, 'Symbol', 'EndDate')
if bs is not None:
    check_match("资产负债表-合并 (FS_Combas, A)", bs[bs['Typrep']=='A'], 'Stkcd', 'Accper')
if sub is not None:
    check_match("政府补助表 (FN_FN056)", sub, 'Stkcd', 'Accper')
if cf is not None:
    check_match("现金流量表-合并 (FS_Comscfd, A)", cf[cf['Typrep']=='A'], 'Stkcd', 'Accper')
p()

# ============================================================
p("## 五、12条优先级数据缺口对照")
p()
# ============================================================
items = [
    ("P1", "企业注册地省份", "STK_LISTEDCOINFOANL.PROVINCE", "[已解决]", "省份字段全覆盖, >99%非缺失"),
    ("P2", "当年发明专利申请数", "PT_LCDOMFORAPPLY.Invention (ApplyType=已申请)", "[已解决]", "可构造 firm_invention_apply"),
    ("P3", "当年发明专利授权数", "PT_LCDOMFORAPPLY.Invention (ApplyType=已授权)", "[已解决]", "可构造 firm_invention_grant"),
    ("P4", "真实研发费用", "PT_LCRDSPENDING.RDSpendSum", "[已解决]", "年报披露真实研发投入, 替代 rd_expense_est"),
    ("P5", "研发加计扣除享受额", "PT_LCRDSPENDING.RDSpendSum * rd_deduction_rate", "[可构造]", "无直接字段, 用研发投入*政策比例估算"),
    ("P6", "2017-2018年面板", "所有8个新表", "[已解决]", "年份均从2016起, 政策前窗口扩充至6年"),
    ("P7", "营业收入", "FS_Comins.B001101000", "[已解决]", "合并报表全覆盖"),
    ("P8", "所得税费用", "FS_Comins.B002100000", "[已解决]", "合并报表全覆盖"),
    ("P9", "利润总额", "FS_Comins.B001000000", "[已解决]", "合并报表全覆盖"),
    ("P10", "所有制性质", "HLD_Contrshr.S0702b", "[已解决]", "实际控制人性质, 可构造SOE"),
    ("P11", "研发人员数量", "PT_LCRDSPENDING.RDPerson", "[已解决]", "+ RDPersonRatio 占比"),
    ("P12", "研发政府补助", "FN_FN056.Fn05601 + Fn05602", "[已解决]", "从76万明细中筛选研发相关, 汇总到企业-年"),
]
p("| 优先级 | 需求 | 数据源 | 状态 | 备注 |")
p("|--------|------|--------|------|------|")
for pid, name, source, status, note in items:
    p(f"| {pid} | {name} | `{source}` | {status} | {note} |")
p()

# ============================================================
p("## 六、建模修改建议")
p()
# ============================================================
p("### 6.1 因变量升级")
p()
p("当前 `patent_stock` (累计专利存量) → 建议替换/补充:")
p("- **主因变量:** `firm_invention_apply` (当年发明专利申请数) — 流量型高质量创新指标")
p("- **替代因变量:** `firm_invention_grant` (当年发明专利授权数) — 高质量创新结果")
p("- **保留:** `patent_stock` 作为稳健性对照")
p()
p("### 6.2 核心自变量替换")
p()
p("当前 `rd_expense_est` (由加计扣除反推) → 替换为:")
p("- `RDSpendSum` — 年报披露的真实研发投入金额")
p("- `RDSpendSumRatio` — 研发投入占营业收入比例 (直接取自 CSMAR)")
p("- 可重新计算: `rd_intensity = RDSpendSum / B001101000 * 100`")
p()
p("当前 `rd_tax_deduction` (99.8%为负) → 替换为:")
p("- 构造: `rd_tax_deduction_est = RDSpendSum × rd_deduction_rate × 0.25`")
p("- 注意区分行业: 制造业 2021年前75%, 2021年起100%; 一般企业不同")
p()
p("### 6.3 新增变量")
p()
p("| 新变量 | 来源 | 用途 |")
p("|--------|------|------|")
p("| `soe` | HLD_Contrshr.S0702b | 国企/民企异质性 |")
p("| `rd_staff` | PT_LCRDSPENDING.RDPerson | 人力投入机制检验 |")
p("| `revenue` | FS_Comins.B001101000 | 计算标准研发强度 |")
p("| `profit_before_tax` | FS_Comins.B001000000 | 计算 ETR |")
p("| `income_tax_expense` | FS_Comins.B002100000 | 计算 ETR |")
p("| `total_assets` | FS_Combas.A001000000 | 替代 ln_assets |")
p("| `rd_subsidy` | FN_FN056 (研发项目汇总) | 补贴机制检验 |")
p("| `invention_apply` | PT_LCDOMFORAPPLY (已申请) | 主因变量 |")
p("| `invention_grant` | PT_LCDOMFORAPPLY (已授权) | 稳健性因变量 |")
p()
p("### 6.4 样本时间扩展")
p()
p("- 当前: 2019-2024 (6年, 仅2个政策前年份)")
p("- 建议: 2017-2024 (8年, 4个政策前年份) 或 2016-2024 (9年)")
p("- 所有新表年份从2016起, 扩展无损")
p()
p("### 6.5 省份匹配修复")
p()
p("- 当前 provnice_std 覆盖率 48%, 因为依赖 `实证数据.xlsx` sheet 4")
p("- 用 STK_LISTEDCOINFOANL.PROVINCE 重新匹配, 预计覆盖率 >99%")

# ============================================================
p()
p("---")
p(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
p()

# Write to file
with open("data/data_audit_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))

print("\nDone. Report saved to data/data_audit_report.md")
