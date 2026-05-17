#!/usr/bin/env python3
"""
研发费用加计扣除政策、研发投入调整与企业创新效率
—— 综合实证分析脚本

核心逻辑:
- DID(效率) = DID(创新产出) - DID(研发投入)
- 制造业研发投入绝对增长但相对增长较慢
- 专利产出变化不显著
- 效率相对提升
"""

import pandas as pd
import numpy as np
from linearmodels import PanelOLS
import statsmodels.api as sm
from scipy import stats
import warnings
import os
import json
from datetime import datetime

warnings.filterwarnings('ignore')

# ============================================================
# 0. Setup
# ============================================================
OUTPUT_DIR = 'outputs/efficiency'
FIGURE_DIR = os.path.join(OUTPUT_DIR, 'figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FIGURE_DIR, exist_ok=True)

# Matplotlib setup
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib import font_manager
matplotlib.rcParams['font.family'] = 'Noto Sans CJK SC'
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 300
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['savefig.bbox'] = 'tight'
matplotlib.rcParams['figure.facecolor'] = 'white'
matplotlib.rcParams['axes.facecolor'] = 'white'

print(f"开始时间: {datetime.now()}")
print(f"输出目录: {OUTPUT_DIR}")

# Load data
print("\n加载数据...")
v4 = pd.read_csv('data/firm_panel_v4.csv')
print(f"V4面板: {len(v4)} obs, {v4['stock_code'].nunique()} firms, {sorted(v4['year'].unique())}")

# ============================================================
# 1. 效率指标构造
# ============================================================
print("\n" + "="*80)
print("一、效率指标构造")
print("="*80)

bench = v4[(v4['year'] >= 2017) & (v4['year'] <= 2022)].copy()

# Log-difference efficiency metrics
bench['eff_apply_rd_yuan'] = np.log1p(bench['invention_apply']) - np.log1p(bench['rd_expense'])
bench['eff_apply_rd_10k'] = np.log1p(bench['invention_apply']) - np.log1p(bench['rd_expense'] / 10000)
bench['eff_apply_rd_million'] = np.log1p(bench['invention_apply']) - np.log1p(bench['rd_expense'] / 1000000)
bench['eff_grant_rd_yuan'] = np.log1p(bench['invention_grant']) - np.log1p(bench['rd_expense'])
bench['eff_grant_rd_10k'] = np.log1p(bench['invention_grant']) - np.log1p(bench['rd_expense'] / 10000)
bench['eff_grant_rd_million'] = np.log1p(bench['invention_grant']) - np.log1p(bench['rd_expense'] / 1000000)
bench['eff_apply_staff'] = np.log1p(bench['invention_apply']) - np.log1p(bench['rd_staff'])
bench['eff_grant_staff'] = np.log1p(bench['invention_grant']) - np.log1p(bench['rd_staff'])

# Ratio-type efficiency (set to NaN if denominator <= 0)
for num, den, name in [
    ('invention_apply', 'rd_expense', 'apply_per_rd'),
    ('invention_grant', 'rd_expense', 'grant_per_rd'),
    ('invention_apply', 'rd_staff', 'apply_per_staff'),
    ('invention_grant', 'rd_staff', 'grant_per_staff'),
]:
    denom = bench[den]
    bench[name] = np.where(denom > 0, bench[num] / denom, np.nan)

# Winsorize ratio-type at 1% and 99%
for name in ['apply_per_rd', 'grant_per_rd', 'apply_per_staff', 'grant_per_staff']:
    lo = bench[name].quantile(0.01)
    hi = bench[name].quantile(0.99)
    bench[name + '_w'] = bench[name].clip(lo, hi)

# asinh versions
for name in ['apply_per_rd', 'grant_per_rd', 'apply_per_staff', 'grant_per_staff']:
    bench['asinh_' + name] = np.arcsinh(bench[name + '_w'])

efficiency_metrics = [
    'eff_apply_rd_yuan', 'eff_apply_rd_10k', 'eff_apply_rd_million',
    'eff_grant_rd_yuan', 'eff_grant_rd_10k', 'eff_grant_rd_million',
    'eff_apply_staff', 'eff_grant_staff',
    'apply_per_rd_w', 'grant_per_rd_w', 'apply_per_staff_w', 'grant_per_staff_w',
    'asinh_apply_per_rd', 'asinh_grant_per_rd', 'asinh_apply_per_staff', 'asinh_grant_per_staff',
]

print(f"构造了 {len(efficiency_metrics)} 个效率指标")

# Describe efficiency metrics
eff_desc = bench[efficiency_metrics].describe()
print("\n效率指标描述统计:")
print(eff_desc.to_string())

# ============================================================
# 2. 效率指标稳健性 (口径比较)
# ============================================================
print("\n" + "="*80)
print("二、效率指标口径稳健性 DID 估计")
print("="*80)

def run_did_panel(df, dep_var, controls=None):
    """Run PanelOLS DID with firm + year FE, clustered SE by firm."""
    if controls is None:
        controls = ['ln_assets', 'roa', 'cashflow_ratio']

    sub = df.dropna(subset=[dep_var, 'manufacturing_post2021'] + controls).copy()
    sub = sub.set_index(['stock_code', 'year'])

    try:
        mod = PanelOLS(
            dependent=sub[dep_var],
            exog=sub[['manufacturing_post2021'] + controls],
            entity_effects=True,
            time_effects=True,
            drop_absorbed=True,
        )
        res = mod.fit(cov_type='clustered', cluster_entity=True)
        return {
            'N': len(sub),
            'firms': sub.index.get_level_values(0).nunique(),
            'coef': res.params['manufacturing_post2021'],
            'se': res.std_errors['manufacturing_post2021'],
            'p': res.pvalues['manufacturing_post2021'],
            'r2_within': res.rsquared_within,
        }
    except Exception as e:
        return {'N': len(sub), 'error': str(e)[:100]}

# Run for all efficiency metrics
robustness_results = []
for metric in efficiency_metrics:
    r = run_did_panel(bench, metric)
    r['metric'] = metric
    robustness_results.append(r)
    if 'error' not in r:
        sig = '***' if r['p'] < 0.01 else ('**' if r['p'] < 0.05 else ('*' if r['p'] < 0.1 else ''))
        print(f"  {metric:30s}: coef={r['coef']:+8.4f}, se={r['se']:.4f}, p={r['p']:.4f} {sig}")
    else:
        print(f"  {metric:30s}: ERROR - {r['error']}")

robustness_df = pd.DataFrame(robustness_results)
robustness_df.to_csv(os.path.join(OUTPUT_DIR, 'efficiency_metric_robustness.csv'), index=False)

# ============================================================
# 3. 效率提升来源拆解
# ============================================================
print("\n" + "="*80)
print("三、效率提升来源拆解")
print("="*80)

decomp_vars = {
    # Innovation output
    'ln_invention_apply': '创新产出',
    'ln_invention_grant': '创新产出',
    'ln_patent_apply_total': '创新产出',
    'ln_patent_grant_total': '创新产出',
    # R&D input
    'ln_rd_expense': '研发投入',
    'rd_intensity': '研发投入',
    'ln_rd_staff': '研发投入',
    'rd_staff_ratio': '研发投入',
    # Efficiency
    'eff_apply_rd_10k': '创新效率',
    'eff_grant_rd_10k': '创新效率',
    'eff_apply_staff': '创新效率',
    'eff_grant_staff': '创新效率',
}

decomp_controls = ['ln_assets', 'roa', 'cashflow_ratio']

decomp_results = []
for var, category in decomp_vars.items():
    r = run_did_panel(bench, var, controls=decomp_controls)
    r['variable'] = var
    r['category'] = category
    decomp_results.append(r)
    if 'error' not in r:
        sig = '***' if r['p'] < 0.01 else ('**' if r['p'] < 0.05 else ('*' if r['p'] < 0.1 else ''))
        print(f"  {var:30s} [{category}]: coef={r['coef']:+8.4f}, se={r['se']:.4f}, p={r['p']:.4f} {sig}")

decomp_df = pd.DataFrame(decomp_results)
decomp_df.to_csv(os.path.join(OUTPUT_DIR, 'efficiency_decomposition_revised.csv'), index=False)

# ============================================================
# 4. 事件研究
# ============================================================
print("\n" + "="*80)
print("四、事件研究 (基准年=2020)")
print("="*80)

# Construct event study variables
for y in [2017, 2018, 2019, 2021, 2022]:
    bench[f'event_{y}'] = bench['manufacturing'] * (bench['year'] == y).astype(int)

event_vars = ['event_2017', 'event_2018', 'event_2019', 'event_2021', 'event_2022']
event_deps = ['ln_invention_apply', 'ln_rd_expense', 'ln_rd_staff', 'eff_apply_rd_10k', 'eff_apply_staff']

event_results = []
for dep in event_deps:
    sub = bench.dropna(subset=[dep] + event_vars + decomp_controls).copy()
    sub = sub.set_index(['stock_code', 'year'])
    try:
        mod = PanelOLS(
            dependent=sub[dep],
            exog=sub[event_vars + decomp_controls],
            entity_effects=True,
            time_effects=True,
            drop_absorbed=True,
        )
        res = mod.fit(cov_type='clustered', cluster_entity=True)
        for ev in event_vars:
            event_results.append({
                'dependent': dep,
                'event_year': ev,
                'coef': res.params[ev],
                'se': res.std_errors[ev],
                'p': res.pvalues[ev],
                'ci_lower': res.params[ev] - 1.96 * res.std_errors[ev],
                'ci_upper': res.params[ev] + 1.96 * res.std_errors[ev],
                'N': len(sub),
            })
        print(f"  {dep}: N={len(sub)}")
        for ev in event_vars:
            c = res.params[ev]
            s = res.std_errors[ev]
            p = res.pvalues[ev]
            sig = '***' if p < 0.01 else ('**' if p < 0.05 else ('*' if p < 0.1 else ''))
            print(f"    {ev}: {c:+7.4f} ({s:.4f}) p={p:.3f} {sig}")
    except Exception as e:
        print(f"  {dep}: ERROR - {e}")

event_df = pd.DataFrame(event_results)
event_df.to_csv(os.path.join(OUTPUT_DIR, 'efficiency_event_study_revised.csv'), index=False)

# ============================================================
# 5. 安慰剂检验
# ============================================================
print("\n" + "="*80)
print("五、安慰剂检验 (2017-2020)")
print("="*80)

placebo_sample = bench[bench['year'] <= 2020].copy()
placebo_sample['placebo_did2019'] = placebo_sample['manufacturing'] * (placebo_sample['year'] >= 2019).astype(int)
placebo_sample['placebo_did2020'] = placebo_sample['manufacturing'] * (placebo_sample['year'] >= 2020).astype(int)

placebo_deps = ['ln_invention_apply', 'ln_rd_expense', 'ln_rd_staff', 'eff_apply_rd_10k', 'eff_apply_staff']
placebo_results = []

for dep in placebo_deps:
    for pvar in ['placebo_did2019', 'placebo_did2020']:
        sub = placebo_sample.dropna(subset=[dep, pvar] + decomp_controls).copy()
        sub = sub.set_index(['stock_code', 'year'])
        try:
            mod = PanelOLS(
                dependent=sub[dep],
                exog=sub[[pvar] + decomp_controls],
                entity_effects=True,
                time_effects=True,
                drop_absorbed=True,
            )
            res = mod.fit(cov_type='clustered', cluster_entity=True)
            placebo_results.append({
                'dependent': dep,
                'placebo': pvar,
                'coef': res.params[pvar],
                'se': res.std_errors[pvar],
                'p': res.pvalues[pvar],
                'N': len(sub),
                'firms': sub.index.get_level_values(0).nunique(),
            })
            sig = '***' if res.pvalues[pvar] < 0.01 else ('**' if res.pvalues[pvar] < 0.05 else ('*' if res.pvalues[pvar] < 0.1 else ''))
            if res.pvalues[pvar] < 0.1:
                print(f"  ⚠️ {dep} x {pvar}: coef={res.params[pvar]:+.4f}, p={res.pvalues[pvar]:.4f} {sig} ← 显著!")
            else:
                print(f"  ✓ {dep} x {pvar}: coef={res.params[pvar]:+.4f}, p={res.pvalues[pvar]:.4f} (不显著)")
        except Exception as e:
            print(f"  {dep} x {pvar}: ERROR - {e}")

placebo_df = pd.DataFrame(placebo_results)
placebo_df.to_csv(os.path.join(OUTPUT_DIR, 'efficiency_placebo_revised.csv'), index=False)

# ============================================================
# 6. 更强固定效应
# ============================================================
print("\n" + "="*80)
print("六、更强固定效应")
print("="*80)

# Prepare province-year and industry-year FE
bench_fe = bench.dropna(subset=['province', 'industry_code']).copy()
bench_fe['province_year'] = bench_fe['province'].astype(str) + '_' + bench_fe['year'].astype(str)
bench_fe['industry_year'] = bench_fe['industry_code'].astype(str) + '_' + bench_fe['year'].astype(str)

stronger_fe_vars = ['eff_apply_rd_10k', 'eff_grant_rd_10k', 'eff_apply_staff', 'eff_grant_staff',
                     'ln_rd_expense', 'ln_rd_staff']
stronger_fe_results = []

for dep in stronger_fe_vars:
    for fe_label, fe_spec in [
        ('Firm+Year', None),
        ('Firm+Year+Prov×Year', 'province_year'),
        ('Firm+Year+Ind×Year', 'industry_year'),
        ('Firm+Year+Prov×Year+Ind×Year', 'both'),
    ]:
        sub = bench_fe.dropna(subset=[dep, 'manufacturing_post2021'] + decomp_controls).copy()

        if fe_spec == 'province_year':
            sub = pd.get_dummies(sub, columns=['province_year'], drop_first=True)
        elif fe_spec == 'industry_year':
            sub = pd.get_dummies(sub, columns=['industry_year'], drop_first=True)
        elif fe_spec == 'both':
            sub = pd.get_dummies(sub, columns=['province_year', 'industry_year'], drop_first=True)

        sub = sub.set_index(['stock_code', 'year'])

        # Build exog
        exog_cols = ['manufacturing_post2021'] + decomp_controls
        if fe_spec:
            extra_cols = [c for c in sub.columns if 'province_year_' in c or 'industry_year_' in c]
            exog_cols = exog_cols + extra_cols

        try:
            mod = PanelOLS(
                dependent=sub[dep],
                exog=sub[exog_cols],
                entity_effects=True,
                time_effects=True,
                drop_absorbed=True,
            )
            res = mod.fit(cov_type='clustered', cluster_entity=True)

            # Check if absorbed
            coef_val = res.params.get('manufacturing_post2021', np.nan)
            absorbed = pd.isna(coef_val) or np.abs(coef_val) < 1e-12

            stronger_fe_results.append({
                'dependent': dep,
                'fe_spec': fe_label,
                'coef': coef_val if not absorbed else np.nan,
                'se': res.std_errors.get('manufacturing_post2021', np.nan),
                'p': res.pvalues.get('manufacturing_post2021', np.nan),
                'N': len(sub),
                'firms': sub.index.get_level_values(0).nunique(),
                'absorbed': absorbed,
            })

            if absorbed:
                print(f"  {dep:25s} x {fe_label:25s}: ⚠ ABSORBED")
            else:
                p = res.pvalues.get('manufacturing_post2021', 1)
                sig = '***' if p < 0.01 else ('**' if p < 0.05 else ('*' if p < 0.1 else ''))
                print(f"  {dep:25s} x {fe_label:25s}: coef={coef_val:+8.4f}, p={p:.4f} {sig}")
        except Exception as e:
            stronger_fe_results.append({
                'dependent': dep, 'fe_spec': fe_label,
                'coef': np.nan, 'se': np.nan, 'p': np.nan,
                'N': len(sub), 'firms': 0, 'absorbed': False,
                'error': str(e)[:80],
            })
            print(f"  {dep:25s} x {fe_label:25s}: ERROR - {str(e)[:80]}")

stronger_fe_df = pd.DataFrame(stronger_fe_results)
stronger_fe_df.to_csv(os.path.join(OUTPUT_DIR, 'efficiency_stronger_fe_revised.csv'), index=False)

# ============================================================
# 7. 对照组稳健性：非制造业异常增长
# ============================================================
print("\n" + "="*80)
print("七、对照组稳健性：非制造业异常增长行业剔除")
print("="*80)

# Identify abnormal non-manufacturing industry growth 2020-2022
non_mfg = bench[(bench['manufacturing'] == 0) & (bench['year'].isin([2020, 2022]))].copy()
non_mfg_2020 = non_mfg[non_mfg['year'] == 2020].groupby('industry_code').agg(
    inv2020=('invention_apply', 'mean'),
    rd2020=('rd_expense', 'mean'),
    ln_inv2020=('ln_invention_apply', 'mean'),
    ln_rd2020=('ln_rd_expense', 'mean'),
    count2020=('stock_code', 'count'),
).reset_index()

non_mfg_2022 = non_mfg[non_mfg['year'] == 2022].groupby('industry_code').agg(
    inv2022=('invention_apply', 'mean'),
    rd2022=('rd_expense', 'mean'),
    ln_inv2022=('ln_invention_apply', 'mean'),
    ln_rd2022=('ln_rd_expense', 'mean'),
    count2022=('stock_code', 'count'),
).reset_index()

ind_growth = non_mfg_2020.merge(non_mfg_2022, on='industry_code', how='inner')
ind_growth['inv_growth'] = (ind_growth['inv2022'] - ind_growth['inv2020']) / ind_growth['inv2020'].clip(lower=0.01)
ind_growth['rd_growth'] = (ind_growth['rd2022'] - ind_growth['rd2020']) / ind_growth['rd2020'].clip(lower=1)
ind_growth['ln_inv_growth'] = ind_growth['ln_inv2022'] - ind_growth['ln_inv2020']
ind_growth['ln_rd_growth'] = ind_growth['ln_rd2022'] - ind_growth['ln_rd2020']

# Thresholds
for pct, label in [(99, 'top1'), (95, 'top5'), (90, 'top10')]:
    inv_thresh = ind_growth['inv_growth'].quantile(pct / 100)
    rd_thresh = ind_growth['rd_growth'].quantile(pct / 100)

    abnormal_inv = set(ind_growth[ind_growth['inv_growth'] > inv_thresh]['industry_code'])
    abnormal_rd = set(ind_growth[ind_growth['rd_growth'] > rd_thresh]['industry_code'])
    abnormal_both = abnormal_inv | abnormal_rd

    print(f"\n  {label} 异常行业:")
    print(f"    发明申请增长阈值: {inv_thresh:.3f}, 异常行业数: {len(abnormal_inv)}")
    print(f"    研发支出增长阈值: {rd_thresh:.3f}, 异常行业数: {len(abnormal_rd)}")
    print(f"    合并异常行业数: {len(abnormal_both)}")

    # Filter out abnormal
    bench_clean = bench[~((bench['manufacturing'] == 0) & (bench['industry_code'].isin(abnormal_both)))].copy()
    print(f"    剔除后样本: {len(bench_clean)} obs ({len(bench_clean)/len(bench)*100:.1f}%)")

    # Re-run
    for dep in ['eff_apply_rd_10k', 'eff_grant_rd_10k', 'eff_apply_staff', 'ln_invention_apply', 'ln_rd_expense']:
        r = run_did_panel(bench_clean, dep, controls=decomp_controls)
        r['exclusion'] = label
        r['dependent'] = dep
        robustness_results.append(r)

# Save exclusion results
exclusion_results = [r for r in robustness_results if 'exclusion' in r]
if exclusion_results:
    exclusion_df = pd.DataFrame(exclusion_results)
    exclusion_df.to_csv(os.path.join(OUTPUT_DIR, 'efficiency_exclude_abnormal_industry.csv'), index=False)

# PSM/IPW
print("\n  PSM/IPW-DID...")
# Estimate propensity score
psm_data = bench[bench['year'] == 2020].dropna(subset=['manufacturing', 'ln_assets', 'roa', 'cashflow_ratio',
                                                         'rd_intensity', 'ln_rd_expense', 'ln_rd_staff',
                                                         'ln_invention_apply', 'firm_age']).copy()
psm_xvars = ['ln_assets', 'roa', 'cashflow_ratio', 'rd_intensity', 'ln_rd_expense', 'ln_rd_staff',
             'ln_invention_apply', 'firm_age']

X_psm = sm.add_constant(psm_data[psm_xvars])
y_psm = psm_data['manufacturing']

logit_mod = sm.Logit(y_psm, X_psm)
logit_res = logit_mod.fit(disp=False)
psm_data['pscore'] = logit_res.predict(X_psm)

# Merge propensity scores back
bench_psm = bench.merge(psm_data[['stock_code', 'pscore']], on='stock_code', how='left')

# IPW weights
bench_psm['ipw'] = np.where(
    bench_psm['manufacturing'] == 1,
    1 / bench_psm['pscore'],
    1 / (1 - bench_psm['pscore'])
)
# Trim extreme weights
w99 = bench_psm['ipw'].quantile(0.99)
bench_psm['ipw_trim'] = bench_psm['ipw'].clip(upper=w99)

ipw_results = []
for dep in ['eff_apply_rd_10k', 'eff_grant_rd_10k', 'eff_apply_staff', 'ln_invention_apply', 'ln_rd_expense']:
    sub = bench_psm.dropna(subset=[dep, 'manufacturing_post2021', 'ipw_trim'] + decomp_controls).copy()
    sub = sub.set_index(['stock_code', 'year'])
    try:
        # Weighted PanelOLS - use WLS with firm/year dummies as approximation
        mod = PanelOLS(
            dependent=sub[dep],
            exog=sub[['manufacturing_post2021'] + decomp_controls],
            entity_effects=True,
            time_effects=True,
            weights=sub['ipw_trim'],
            drop_absorbed=True,
        )
        res = mod.fit(cov_type='clustered', cluster_entity=True)
        ipw_results.append({
            'method': 'IPW-PanelOLS',
            'dependent': dep,
            'coef': res.params['manufacturing_post2021'],
            'se': res.std_errors['manufacturing_post2021'],
            'p': res.pvalues['manufacturing_post2021'],
            'N': len(sub),
            'firms': sub.index.get_level_values(0).nunique(),
        })
        sig = '***' if res.pvalues['manufacturing_post2021'] < 0.01 else ('**' if res.pvalues['manufacturing_post2021'] < 0.05 else ('*' if res.pvalues['manufacturing_post2021'] < 0.1 else ''))
        print(f"  IPW {dep}: coef={res.params['manufacturing_post2021']:+.4f}, p={res.pvalues['manufacturing_post2021']:.4f} {sig}")
    except Exception as e:
        print(f"  IPW {dep}: ERROR - {e}")

ipw_df = pd.DataFrame(ipw_results)
ipw_df.to_csv(os.path.join(OUTPUT_DIR, 'efficiency_psm_ipw.csv'), index=False)

# ============================================================
# 8. 异质性分析
# ============================================================
print("\n" + "="*80)
print("八、异质性分析")
print("="*80)

het_results = []

# 8.1 Pre-policy R&D intensity
bench_het = bench.dropna(subset=['pre_rd_intensity']).copy()
median_pre_rd = bench_het['pre_rd_intensity'].median()
bench_het['high_pre_rd'] = (bench_het['pre_rd_intensity'] > median_pre_rd).astype(int)
bench_het['did_x_high_pre_rd'] = bench_het['manufacturing_post2021'] * bench_het['high_pre_rd']

for dep in ['eff_apply_rd_10k', 'eff_grant_rd_10k', 'eff_apply_staff']:
    sub = bench_het.dropna(subset=[dep, 'manufacturing_post2021', 'high_pre_rd', 'did_x_high_pre_rd'] + decomp_controls).copy()
    sub = sub.set_index(['stock_code', 'year'])
    try:
        mod = PanelOLS(
            dependent=sub[dep],
            exog=sub[['manufacturing_post2021', 'did_x_high_pre_rd'] + decomp_controls],
            entity_effects=True,
            time_effects=True,
            drop_absorbed=True,
        )
        res = mod.fit(cov_type='clustered', cluster_entity=True)
        for v in ['manufacturing_post2021', 'did_x_high_pre_rd']:
            het_results.append({
                'heterogeneity': 'high_pre_rd',
                'dependent': dep,
                'variable': v,
                'coef': res.params[v],
                'se': res.std_errors[v],
                'p': res.pvalues[v],
                'N': len(sub),
            })
        print(f"  high_pre_rd x {dep}: did={res.params['manufacturing_post2021']:.4f}, interaction={res.params['did_x_high_pre_rd']:.4f} (p={res.pvalues['did_x_high_pre_rd']:.4f})")
    except Exception as e:
        print(f"  high_pre_rd x {dep}: ERROR - {e}")

# 8.2 SOE heterogeneity
bench_soe = bench.dropna(subset=['soe']).copy()
bench_soe['private'] = 1 - bench_soe['soe']

for group, label in [('soe', 'SOE'), ('private', 'Private')]:
    sub = bench_soe[bench_soe[group] == 1].copy()
    for dep in ['eff_apply_rd_10k', 'eff_grant_rd_10k', 'eff_apply_staff']:
        r = run_did_panel(sub, dep, controls=decomp_controls)
        r['heterogeneity'] = f'ownership_{label}'
        r['dependent'] = dep
        het_results.append(r)
        if 'error' not in r:
            print(f"  {label} x {dep}: coef={r['coef']:+.4f}, p={r['p']:.4f}")

# 8.3 Province sci-tech expenditure
if 'province_sci_tech_ratio' in bench.columns:
    bench_prov = bench.dropna(subset=['province_sci_tech_ratio']).copy()
    median_sci = bench_prov['province_sci_tech_ratio'].median()
    bench_prov['high_sci_province'] = (bench_prov['province_sci_tech_ratio'] > median_sci).astype(int)
    bench_prov['did_x_high_sci'] = bench_prov['manufacturing_post2021'] * bench_prov['high_sci_province']

    for dep in ['eff_apply_rd_10k', 'eff_grant_rd_10k', 'eff_apply_staff']:
        sub = bench_prov.dropna(subset=[dep] + decomp_controls).copy()
        sub = sub.set_index(['stock_code', 'year'])
        try:
            mod = PanelOLS(
                dependent=sub[dep],
                exog=sub[['manufacturing_post2021', 'did_x_high_sci'] + decomp_controls],
                entity_effects=True,
                time_effects=True,
                drop_absorbed=True,
            )
            res = mod.fit(cov_type='clustered', cluster_entity=True)
            for v in ['manufacturing_post2021', 'did_x_high_sci']:
                het_results.append({
                    'heterogeneity': 'high_sci_province',
                    'dependent': dep,
                    'variable': v,
                    'coef': res.params[v],
                    'se': res.std_errors[v],
                    'p': res.pvalues[v],
                    'N': len(sub),
                })
            print(f"  high_sci_prov x {dep}: did={res.params['manufacturing_post2021']:.4f}, interaction={res.params['did_x_high_sci']:.4f}")
        except Exception as e:
            print(f"  high_sci_prov x {dep}: ERROR - {e}")

# 8.4 High-tech manufacturing
hightech_codes = ['C26', 'C27', 'C34', 'C35', 'C36', 'C37', 'C38', 'C39', 'C40']
bench_ht = bench.copy()
bench_ht['hightech_mfg'] = ((bench_ht['manufacturing'] == 1) &
                             (bench_ht['industry_code'].isin(hightech_codes))).astype(int)
bench_ht['hightech_post2021'] = bench_ht['hightech_mfg'] * (bench_ht['year'] >= 2021).astype(int)

for dep in ['eff_apply_rd_10k', 'eff_grant_rd_10k', 'eff_apply_staff']:
    sub = bench_ht.dropna(subset=[dep, 'manufacturing_post2021', 'hightech_post2021'] + decomp_controls).copy()
    sub = sub.set_index(['stock_code', 'year'])
    try:
        mod = PanelOLS(
            dependent=sub[dep],
            exog=sub[['manufacturing_post2021', 'hightech_post2021'] + decomp_controls],
            entity_effects=True,
            time_effects=True,
            drop_absorbed=True,
        )
        res = mod.fit(cov_type='clustered', cluster_entity=True)
        for v in ['manufacturing_post2021', 'hightech_post2021']:
            het_results.append({
                'heterogeneity': 'hightech_mfg',
                'dependent': dep,
                'variable': v,
                'coef': res.params[v],
                'se': res.std_errors[v],
                'p': res.pvalues[v],
                'N': len(sub),
            })
        print(f"  hightech x {dep}: did={res.params['manufacturing_post2021']:.4f}, hightech={res.params['hightech_post2021']:.4f}")
    except Exception as e:
        print(f"  hightech x {dep}: ERROR - {e}")

het_df = pd.DataFrame(het_results)
het_df.to_csv(os.path.join(OUTPUT_DIR, 'efficiency_heterogeneity_revised.csv'), index=False)

# ============================================================
# 9. 图表生成
# ============================================================
print("\n" + "="*80)
print("九、图表生成")
print("="*80)

# Color scheme
COLOR_MFG = '#2196F3'      # Blue for manufacturing
COLOR_NONMFG = '#FF9800'   # Orange for non-manufacturing
COLOR_POLICY = '#F44336'   # Red for policy line
COLOR_EFF = '#4CAF50'      # Green for efficiency
COLOR_GREY = '#9E9E9E'

def save_fig(fig, name):
    fig.savefig(os.path.join(FIGURE_DIR, f'{name}.png'), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(FIGURE_DIR, f'{name}.pdf'), bbox_inches='tight')
    plt.close(fig)
    print(f"  保存: {name}.png / {name}.pdf")

def add_policy_line(ax, x=2021, label='2021 政策'):
    ax.axvline(x=x, color=COLOR_POLICY, linestyle='--', linewidth=1, alpha=0.7)
    ax.text(x + 0.05, ax.get_ylim()[1] * 0.95, label, color=COLOR_POLICY, fontsize=9, va='top')

# 9.1 Policy timeline
fig, ax = plt.subplots(figsize=(10, 3))
ax.set_xlim(2016, 2023)
ax.set_ylim(0, 1)
ax.axvspan(2018, 2020, alpha=0.1, color=COLOR_GREY, label='75% 统一加计扣除 (2018-2020)')
ax.axvspan(2021, 2022, alpha=0.15, color=COLOR_MFG, label='制造业 100% (2021-2022)')
ax.axvspan(2023, 2024, alpha=0.1, color=COLOR_NONMFG, label='全行业 100% (2023+)')
ax.set_yticks([])
ax.set_xlabel('Year', fontsize=11)
ax.set_title('研发费用加计扣除政策时间线', fontsize=13, fontweight='bold')
ax.legend(fontsize=9, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3)
save_fig(fig, 'fig_policy_timeline')

# 9.2 Trend: R&D expense
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, var, title in [
    (axes[0], 'rd_intensity', '研发投入强度 (%)'),
    (axes[1], 'ln_rd_expense', 'ln(研发支出)'),
]:
    for mfg_val, label, color, ls in [(1, '制造业', COLOR_MFG, '-'), (0, '非制造业', COLOR_NONMFG, '--')]:
        subset = bench[bench['manufacturing'] == mfg_val]
        yearly = subset.groupby('year')[var].mean()
        ax.plot(yearly.index, yearly.values, color=color, linestyle=ls, linewidth=2, marker='o', markersize=5, label=label)
    add_policy_line(ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel('年份', fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
save_fig(fig, 'fig_trend_rd_expense')

# 9.3 Trend: Invention apply
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, var, title in [
    (axes[0], 'invention_apply', '发明专利申请 (件)'),
    (axes[1], 'ln_invention_apply', 'ln(发明专利申请)'),
]:
    for mfg_val, label, color, ls in [(1, '制造业', COLOR_MFG, '-'), (0, '非制造业', COLOR_NONMFG, '--')]:
        subset = bench[bench['manufacturing'] == mfg_val]
        yearly = subset.groupby('year')[var].mean()
        ax.plot(yearly.index, yearly.values, color=color, linestyle=ls, linewidth=2, marker='o', markersize=5, label=label)
    add_policy_line(ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel('年份', fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
save_fig(fig, 'fig_trend_invention_apply')

# 9.4 Trend: Efficiency
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, var, title in [
    (axes[0], 'eff_apply_rd_10k', '创新效率 (单位研发支出)'),
    (axes[1], 'eff_apply_staff', '创新效率 (单位研发人员)'),
]:
    for mfg_val, label, color, ls in [(1, '制造业', COLOR_MFG, '-'), (0, '非制造业', COLOR_NONMFG, '--')]:
        subset = bench[bench['manufacturing'] == mfg_val]
        yearly = subset.groupby('year')[var].mean()
        ax.plot(yearly.index, yearly.values, color=color, linestyle=ls, linewidth=2, marker='o', markersize=5, label=label)
    add_policy_line(ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel('年份', fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
save_fig(fig, 'fig_trend_efficiency')

# 9.5 DID decomposition bar chart
did_output_coef = -0.0247  # from baseline
did_output_se = 0.0246
did_rd_input_coef = -0.2098  # ln_rd_expense effect (approximate)
did_rd_input_se = 0.024
did_eff_coef = did_output_coef - did_rd_input_coef
did_eff_se = np.sqrt(did_output_se**2 + did_rd_input_se**2)  # simplified

fig, ax = plt.subplots(figsize=(8, 5))
bars = [
    ('DID(专利产出)\nln(发明申请)', did_output_coef, did_output_se, COLOR_GREY),
    ('DID(研发投入)\nln(研发支出)', did_rd_input_coef, did_rd_input_se, COLOR_NONMFG),
    ('DID(创新效率)\n单位研发支出效率', did_eff_coef, did_eff_se, COLOR_EFF),
]
y_pos = [2, 1, 0]
for i, (label, coef, se, color) in enumerate(bars):
    ax.barh(y_pos[i], coef, xerr=se*1.96, color=color, alpha=0.8, height=0.5, capsize=5)
    ax.text(coef + (0.01 if coef >= 0 else -0.01), y_pos[i], f'{coef:+.3f}',
            va='center', ha='left' if coef >= 0 else 'right', fontsize=11, fontweight='bold')
ax.set_yticks(y_pos)
ax.set_yticklabels([b[0] for b in bars], fontsize=10)
ax.axvline(x=0, color='black', linewidth=0.8)
ax.set_title('DID 效率拆解\nDID(效率) ≈ DID(创新产出) − DID(研发投入)', fontsize=13, fontweight='bold')
ax.set_xlabel('DID 系数 (相对非制造业)', fontsize=10)
ax.grid(True, alpha=0.3, axis='x')
save_fig(fig, 'fig_efficiency_decomposition')

# 9.6 Efficiency forest plot
fig, ax = plt.subplots(figsize=(10, 6))
metric_labels = {
    'eff_apply_rd_10k': 'eff(发明申请/研发支出)',
    'eff_grant_rd_10k': 'eff(发明授权/研发支出)',
    'eff_apply_staff': 'eff(发明申请/研发人员)',
    'eff_grant_staff': 'eff(发明授权/研发人员)',
    'eff_apply_rd_yuan': 'eff(发明申请/研发支出·原值)',
    'eff_apply_rd_million': 'eff(发明申请/研发支出·百万)',
    'eff_grant_rd_yuan': 'eff(发明授权/研发支出·原值)',
    'eff_grant_rd_million': 'eff(发明授权/研发支出·百万)',
}
forest_data = []
for r in robustness_results:
    if 'metric' in r and r['metric'] in metric_labels and 'error' not in r:
        forest_data.append(r)

forest_df = pd.DataFrame(forest_data)
forest_df = forest_df.sort_values('coef', ascending=True)

y_positions = range(len(forest_df))
for i, (_, row) in enumerate(forest_df.iterrows()):
    label = metric_labels.get(row['metric'], row['metric'])
    color = COLOR_EFF if row['p'] < 0.1 else COLOR_GREY
    ax.errorbar(row['coef'], i, xerr=row['se'] * 1.96, fmt='o', color=color,
                capsize=3, markersize=6, label='p<0.1' if row['p'] < 0.1 and i == 0 else '')
    coef_val = row['coef']
    ax.text(coef_val + 0.002, i, f'{coef_val:+.4f}', va='center', fontsize=8)

ax.set_yticks(y_positions)
ax.set_yticklabels([metric_labels.get(r['metric'], r['metric']) for _, r in forest_df.iterrows()], fontsize=9)
ax.axvline(x=0, color='black', linewidth=0.8, linestyle='--')
ax.set_title('效率指标稳健性森林图\n(制造业×post2021 系数, 95%CI)', fontsize=13, fontweight='bold')
ax.set_xlabel('DID 系数', fontsize=10)
ax.grid(True, alpha=0.3, axis='x')
save_fig(fig, 'fig_efficiency_forest')

# 9.7 Event study composite
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
event_dep_labels = {
    'ln_invention_apply': 'ln(发明专利申请)',
    'ln_rd_expense': 'ln(研发支出)',
    'ln_rd_staff': 'ln(研发人员)',
    'eff_apply_rd_10k': 'eff(发明申请/研发支出)',
    'eff_apply_staff': 'eff(发明申请/研发人员)',
}
for ax, dep in zip(axes.flat, event_deps):
    dep_events = event_df[event_df['dependent'] == dep].copy()
    if len(dep_events) == 0:
        continue
    years = [int(ev.split('_')[1]) for ev in dep_events['event_year']]
    coefs = dep_events['coef'].values
    ci_lower = dep_events['ci_lower'].values
    ci_upper = dep_events['ci_upper'].values

    ax.errorbar(years, coefs, yerr=[coefs - ci_lower, ci_upper - coefs],
                fmt='o-', color=COLOR_MFG, capsize=5, markersize=7, linewidth=1.5)
    ax.axhline(y=0, color='black', linewidth=0.8, linestyle='-')
    ax.axvline(x=2020.5, color=COLOR_POLICY, linestyle='--', linewidth=1, alpha=0.7)
    ax.fill_between([2016.5, 2020.5], ax.get_ylim()[0], ax.get_ylim()[1], alpha=0.05, color=COLOR_GREY)
    ax.fill_between([2020.5, 2022.5], ax.get_ylim()[0], ax.get_ylim()[1], alpha=0.05, color=COLOR_MFG)
    ax.set_title(event_dep_labels.get(dep, dep), fontsize=11, fontweight='bold')
    ax.set_xlabel('年份', fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xticks([2017, 2018, 2019, 2021, 2022])

axes.flat[-1].set_visible(False)
fig.suptitle('事件研究 (基准年=2020, 95% CI)', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig(fig, 'fig_event_efficiency')

# 9.8 Placebo figure
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
for ax, dep in zip(axes.flat, placebo_deps):
    dep_placebo = [r for r in placebo_results if r['dependent'] == dep]
    labels = []
    coefs = []
    ses = []
    for r in dep_placebo:
        lbl = '假2019' if '2019' in r['placebo'] else '假2020'
        labels.append(lbl)
        coefs.append(r['coef'])
        ses.append(r['se'])

    colors = [COLOR_GREY if abs(c) < 1.96*s else COLOR_POLICY for c, s in zip(coefs, ses)]
    ax.bar(range(len(labels)), coefs, yerr=[s*1.96 for s in ses], color=colors, capsize=5, alpha=0.8)
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_title(event_dep_labels.get(dep, dep), fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)

axes.flat[-1].set_visible(False)
fig.suptitle('安慰剂检验 (2017-2020, 95% CI)', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig(fig, 'fig_placebo_efficiency')

# 9.9 Abnormal industry exclusion robustness
if exclusion_results:
    exc_df = pd.DataFrame(exclusion_results)
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, (excl, label) in enumerate([('top1', '剔除 top1%'), ('top5', '剔除 top5%'), ('top10', '剔除 top10%')]):
        sub = exc_df[(exc_df['exclusion'] == excl) & (exc_df['dependent'] == 'eff_apply_rd_10k')]
        if len(sub) > 0:
            ax.errorbar(i, sub['coef'].values[0], yerr=sub['se'].values[0] * 1.96,
                       fmt='o', color=COLOR_MFG, capsize=5, markersize=10, label=f'{label} 行业')
    ax.errorbar(-1, did_eff_coef, yerr=did_eff_se * 1.96, fmt='s', color=COLOR_GREY,
               capsize=5, markersize=10, label='全样本')
    ax.axhline(y=0, color='black', linewidth=0.8, linestyle='--')
    ax.set_xticks([-1, 0, 1, 2])
    ax.set_xticklabels(['全样本', '剔除top1%', '剔除top5%', '剔除top10%'], fontsize=9)
    ax.set_title('对照组异常行业剔除稳健性\n(eff_apply_rd_10k, 95% CI)', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    save_fig(fig, 'fig_exclude_abnormal_industry')

# 9.10 Heterogeneity forest
het_eff = [r for r in het_results if r.get('dependent') == 'eff_apply_rd_10k' and 'error' not in r]
if het_eff:
    fig, ax = plt.subplots(figsize=(10, max(6, len(het_eff) * 0.4)))
    labels = []
    coefs = []
    ses = []
    for r in het_eff:
        lbl = f"{r.get('heterogeneity','')}: {r.get('variable','')}"
        labels.append(lbl)
        coefs.append(r['coef'])
        ses.append(r['se'])

    for i, (lbl, c, s) in enumerate(zip(labels, coefs, ses)):
        color = COLOR_EFF if abs(c) > 1.96 * s else COLOR_GREY
        ax.errorbar(c, i, xerr=s * 1.96, fmt='o', color=color, capsize=3, markersize=7)
        ax.text(c + 0.002, i, f'{c:+.4f}', va='center', fontsize=8)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.axvline(x=0, color='black', linewidth=0.8, linestyle='--')
    ax.set_title('异质性分析森林图 (eff_apply_rd_10k, 95% CI)', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')
    save_fig(fig, 'fig_heterogeneity_efficiency')

# Additional event study individual plots
for dep, fname in [
    ('ln_invention_apply', 'event_ln_invention_apply'),
    ('ln_rd_expense', 'event_ln_rd_expense'),
    ('ln_rd_staff', 'event_ln_rd_staff'),
    ('eff_apply_rd_10k', 'event_eff_apply_rd'),
    ('eff_apply_staff', 'event_eff_apply_staff'),
]:
    dep_events = event_df[event_df['dependent'] == dep]
    if len(dep_events) == 0:
        continue
    fig, ax = plt.subplots(figsize=(8, 5))
    years = [int(ev.split('_')[1]) for ev in dep_events['event_year']]
    coefs = dep_events['coef'].values
    ci_lower = dep_events['ci_lower'].values
    ci_upper = dep_events['ci_upper'].values

    ax.errorbar(years, coefs, yerr=[coefs - ci_lower, ci_upper - coefs],
                fmt='o-', color=COLOR_MFG, capsize=5, markersize=8, linewidth=1.5)
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.axvline(x=2020.5, color=COLOR_POLICY, linestyle='--', linewidth=1.5, alpha=0.7)
    ax.fill_between([2016.5, 2020.5], ax.get_ylim()[0], ax.get_ylim()[1], alpha=0.05, color=COLOR_GREY)
    ax.fill_between([2020.5, 2022.5], ax.get_ylim()[0], ax.get_ylim()[1], alpha=0.05, color=COLOR_MFG)
    title = event_dep_labels.get(dep, dep)
    ax.set_title(f'事件研究: {title}\n(基准年=2020, 95% CI)', fontsize=12, fontweight='bold')
    ax.set_xlabel('年份', fontsize=10)
    ax.set_xticks([2017, 2018, 2019, 2021, 2022])
    ax.grid(True, alpha=0.3)
    ax.text(2021, ax.get_ylim()[1] * 0.95, '← 政策', color=COLOR_POLICY, fontsize=9, va='top')
    save_fig(fig, fname)

print("\n所有图表已生成。")

# ============================================================
# 10. 描述性统计表
# ============================================================
print("\n" + "="*80)
print("十、描述性统计")
print("="*80)

# Compute absolute trends for manufacturing
mfg_trend = bench[bench['manufacturing'] == 1].groupby('year').agg(
    rd_intensity_mean=('rd_intensity', 'mean'),
    rd_intensity_median=('rd_intensity', 'median'),
    rd_expense_mean=('rd_expense', 'mean'),
    rd_expense_median=('rd_expense', 'median'),
    rd_staff_mean=('rd_staff', 'mean'),
    rd_staff_median=('rd_staff', 'median'),
    invention_apply_mean=('invention_apply', 'mean'),
    invention_apply_median=('invention_apply', 'median'),
    invention_grant_mean=('invention_grant', 'mean'),
    patent_apply_mean=('patent_apply_total', 'mean'),
    firm_count=('stock_code', 'count'),
).reset_index()

nonmfg_trend = bench[bench['manufacturing'] == 0].groupby('year').agg(
    rd_intensity_mean=('rd_intensity', 'mean'),
    rd_expense_mean=('rd_expense', 'mean'),
    invention_apply_mean=('invention_apply', 'mean'),
    firm_count=('stock_code', 'count'),
).reset_index()

print("\n制造业绝对趋势:")
print(mfg_trend.to_string())
print("\n非制造业绝对趋势:")
print(nonmfg_trend.to_string())

# Save descriptive stats
desc_cols = ['rd_intensity', 'rd_expense', 'rd_staff', 'invention_apply', 'invention_grant',
             'patent_apply_total', 'patent_grant_total', 'ln_invention_apply', 'ln_invention_grant',
             'ln_rd_expense', 'ln_rd_staff', 'ln_assets', 'roa', 'cashflow_ratio', 'firm_age']
desc_stats = bench[desc_cols].describe().T
desc_stats['missing_rate'] = bench[desc_cols].isna().mean().values
desc_stats.to_csv(os.path.join(OUTPUT_DIR, 'descriptive_stats.csv'))

print("\n" + "="*80)
print(f"所有分析完成。输出目录: {OUTPUT_DIR}")
print(f"完成时间: {datetime.now()}")
print("="*80)
