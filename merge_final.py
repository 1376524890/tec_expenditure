import pandas as pd
import numpy as np

# ============================================
# 1. 加载企业主数据
# ============================================
firm = pd.read_excel('data/实证数据.xlsx', sheet_name=7)
firm.columns = ['stock_code', 'firm_name', 'year', 'rd_tax_deduction', 'patent_stock',
                'rd_intensity', 'industry_code', 'industry_name',
                'total_assets_ln', 'roa', 'lev', 'firm_age', 'dual_position']
firm['stock_code'] = firm['stock_code'].astype(str).str.zfill(6)
for col in ['year', 'rd_tax_deduction', 'patent_stock', 'rd_intensity',
            'total_assets_ln', 'roa', 'lev', 'firm_age']:
    firm[col] = pd.to_numeric(firm[col], errors='coerce')

# ============================================
# 2. 研发补助 (未合并过的数据!)
# ============================================
rd_sub = pd.read_excel('data/实证数据.xlsx', sheet_name=1)
rd_sub.columns = ['stock_code', 'end_date', 'gov_subsidy_rd']
# Remove header/string rows
rd_sub = rd_sub[pd.to_numeric(rd_sub['gov_subsidy_rd'], errors='coerce').notna()].copy()
rd_sub['year'] = pd.to_datetime(rd_sub['end_date'], format='mixed').dt.year
rd_sub['stock_code'] = rd_sub['stock_code'].astype(str).str.zfill(6)
rd_sub['gov_subsidy_rd'] = pd.to_numeric(rd_sub['gov_subsidy_rd'], errors='coerce')
rd_sub = rd_sub.groupby(['stock_code', 'year'])['gov_subsidy_rd'].sum().reset_index()

# ============================================
# 3. 省级IP保护指数 (未合并过!)
# ============================================
ip = pd.read_excel('data/实证数据.xlsx', sheet_name=5, header=None)
ip_data = []
for i in range(1, 32):
    row = ip.iloc[i]
    prov_name = str(row[1]).strip()
    score_22 = pd.to_numeric(row[2], errors='coerce')
    score_21 = pd.to_numeric(row[3], errors='coerce')
    ip_data.append({'province_short': prov_name, 'ip_score_2022': score_22, 'ip_score_2021': score_21})
ip_df = pd.DataFrame(ip_data)

# 省份映射
short_to_full = {
    '北京': '北京市', '天津': '天津市', '河北': '河北省', '山西': '山西省',
    '内蒙古': '内蒙古自治区', '辽宁': '辽宁省', '吉林': '吉林省', '黑龙江': '黑龙江省',
    '上海': '上海市', '江苏': '江苏省', '浙江': '浙江省', '安徽': '安徽省',
    '福建': '福建省', '江西': '江西省', '山东': '山东省', '河南': '河南省',
    '湖北': '湖北省', '湖南': '湖南省', '广东': '广东省', '广西': '广西壮族自治区',
    '海南': '海南省', '重庆': '重庆市', '四川': '四川省', '贵州': '贵州省',
    '云南': '云南省', '西藏': '西藏自治区', '陕西': '陕西省', '甘肃': '甘肃省',
    '青海': '青海省', '宁夏': '宁夏回族自治区', '新疆': '新疆维吾尔自治区',
}
ip_df['province_std'] = ip_df['province_short'].map(short_to_full)

# ============================================
# 4. 行业+省份
# ============================================
industry = pd.read_excel('data/实证数据.xlsx', sheet_name=4)
industry = industry.rename(columns={'Symbol': 'stock_code', 'ProvinceName': 'province'})
industry['stock_code'] = industry['stock_code'].astype(str).str.zfill(6)
industry = industry[['stock_code', 'province']].drop_duplicates(subset=['stock_code'])

# ============================================
# 5. 省级面板
# ============================================
prov = pd.read_csv('data/provincial_panel_full.csv')
prov_vars = ['province', 'year', 'gdp', 'fiscal_expenditure', 'fiscal_sci_tech_exp',
             'sci_tech_exp_ratio', 'invention_apply', 'invention_grant',
             'patent_apply_total', 'patent_grant_total', 'tech_market_turnover']

# ============================================
# 合并
# ============================================
print("Step 1: 合并研发补助...")
firm = firm.merge(rd_sub, on=['stock_code', 'year'], how='left')
n = firm['gov_subsidy_rd'].notna().sum()
print(f"  覆盖: {n}/{len(firm)} ({n/len(firm)*100:.0f}%)")

print("Step 2: 合并省份...")
firm = firm.merge(industry, on='stock_code', how='left')
firm['province_std'] = firm['province'].map(short_to_full).fillna(firm['province'])

print("Step 3: 合并省级宏观数据...")
prov_sel = prov[prov_vars].rename(columns={
    'province': 'province_std', 'gdp': 'province_gdp',
    'fiscal_expenditure': 'province_budget_exp',
    'fiscal_sci_tech_exp': 'province_sci_tech_exp'
})
firm = firm.merge(prov_sel, on=['province_std', 'year'], how='left')

print("Step 4: 合并IP保护指数...")
for _, ip_row in ip_df.iterrows():
    ps = ip_row['province_std']
    if pd.isna(ps):
        continue
    mask = (firm['province_std'] == ps) & (firm['year'] >= 2021)
    firm.loc[mask, 'ip_protection_score'] = ip_row['ip_score_2022']
    mask = (firm['province_std'] == ps) & (firm['year'] <= 2020)
    firm.loc[mask, 'ip_protection_score'] = ip_row['ip_score_2021']

# ============================================
# 构造变量
# ============================================
print("Step 5: 构造变量...")
firm['manufacturing'] = firm['industry_name'].str.contains('制造', na=False).astype(int)
firm['post2021'] = (firm['year'] >= 2021).astype(int)
firm['post2022'] = (firm['year'] >= 2022).astype(int)
firm['post2023'] = (firm['year'] >= 2023).astype(int)
firm['manufacturing_post2021'] = firm['manufacturing'] * firm['post2021']
firm['manufacturing_post2022'] = firm['manufacturing'] * firm['post2022']

# 加计扣除比例
firm['rd_deduction_rate'] = 0.75
firm.loc[(firm['year'] >= 2021) & (firm['manufacturing'] == 1), 'rd_deduction_rate'] = 1.0
firm.loc[firm['year'] >= 2023, 'rd_deduction_rate'] = 1.0

# 估算研发费用 (从加计扣除额反推)
firm['rd_expense_est'] = np.abs(firm['rd_tax_deduction']) / (firm['rd_deduction_rate'] * 0.25)

# 对数化
firm['ln_assets'] = pd.to_numeric(firm['total_assets_ln'], errors='coerce')
firm['ln_gdp_prov'] = np.log(pd.to_numeric(firm['province_gdp'], errors='coerce'))
firm['ln_rd_expense_est'] = np.log(firm['rd_expense_est'].clip(lower=1))

# Winsorize top/bottom 1%
for col in ['rd_intensity', 'roa', 'lev']:
    v = firm[col].dropna()
    if len(v) > 0:
        lo, hi = v.quantile(0.01), v.quantile(0.99)
        firm[col] = firm[col].clip(lo, hi)

# ============================================
# 保存
# ============================================
firm = firm[firm['year'].between(2019, 2024)]

col_order = [
    'stock_code', 'firm_name', 'year',
    'industry_code', 'industry_name', 'manufacturing', 'province_std',
    'rd_intensity', 'rd_tax_deduction', 'rd_expense_est',
    'patent_stock',
    'gov_subsidy_rd', 'rd_deduction_rate',
    'ln_assets', 'roa', 'lev', 'firm_age', 'dual_position',
    'post2021', 'post2022', 'post2023', 'manufacturing_post2021', 'manufacturing_post2022',
    'province_gdp', 'ln_gdp_prov', 'province_budget_exp', 'province_sci_tech_exp',
    'sci_tech_exp_ratio', 'ip_protection_score',
    'invention_apply', 'invention_grant', 'patent_apply_total', 'patent_grant_total',
    'tech_market_turnover',
]
available_cols = [c for c in col_order if c in firm.columns]
firm = firm[available_cols]

firm.to_csv('data/firm_panel_final.csv', index=False, encoding='utf-8-sig')
firm.to_excel('data/firm_panel_final.xlsx', index=False)

print(f"\n{'='*60}")
print(f"Final: {len(firm)} obs x {len(firm.columns)} vars")
print(f"Firms: {firm['stock_code'].nunique()} (mfg: {firm[firm['manufacturing']==1]['stock_code'].nunique()})")
print(f"Years: {int(firm['year'].min())}-{int(firm['year'].max())}")
print(f"\nVariable coverage:")
for col in firm.columns:
    pct = firm[col].notna().sum() / len(firm) * 100
    if pct < 100:
        bar = '#' * int(pct/4) + '.' * (25 - int(pct/4))
        print(f'  {col:28s} [{bar}] {pct:.0f}%')

print(f"\nSaved: data/firm_panel_final.csv, data/firm_panel_final.xlsx")
