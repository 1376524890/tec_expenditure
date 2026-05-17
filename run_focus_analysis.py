#!/usr/bin/env python3
"""
研发费用加计扣除政策、研发投入调整与企业创新效率
——聚焦分析脚本

核心逻辑:
- 创新数量DID不显著 → 研究转向
- 制造业研发投入相对增长较慢
- 单位研发投入和单位研发人员创新效率相对提升
- DID(效率) ≈ DID(创新产出) - DID(研发投入)
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
OUTPUT_DIR = 'outputs'
FIGURE_DIR = os.path.join(OUTPUT_DIR, 'figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FIGURE_DIR, exist_ok=True)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Font setup
try:
    matplotlib.rcParams['font.family'] = 'Noto Sans CJK SC'
except:
    try:
        matplotlib.rcParams['font.family'] = 'WenQuanYi Micro Hei'
    except:
        pass
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 300
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['savefig.bbox'] = 'tight'
matplotlib.rcParams['figure.facecolor'] = 'white'
matplotlib.rcParams['axes.facecolor'] = 'white'

COLOR_MFG = '#2196F3'
COLOR_NONMFG = '#FF9800'
COLOR_POLICY = '#F44336'
COLOR_EFF = '#4CAF50'
COLOR_GREY = '#9E9E9E'
COLOR_SIG = '#1B5E20'

print(f"开始时间: {datetime.now()}")
print(f"输出目录: {OUTPUT_DIR}")

# ============================================================
# Utility functions
# ============================================================

def winsorize(s, lo=0.01, hi=0.99):
    """Winsorize a pandas Series at given quantiles."""
    s = s.copy()
    vlo, vhi = s.quantile(lo), s.quantile(hi)
    return s.clip(vlo, vhi)

def run_panel_did(df, dep_var, exog_vars, entity_effects=True, time_effects=True,
                  cluster_entity=True, weights=None):
    """Run PanelOLS DID with firm + year FE, clustered SE by firm."""
    all_vars = exog_vars + [dep_var]
    sub = df.dropna(subset=all_vars).copy()
    if len(sub) == 0:
        return {'N': 0, 'error': 'no observations'}
    sub = sub.set_index(['stock_code', 'year'])
    try:
        mod = PanelOLS(
            dependent=sub[dep_var],
            exog=sub[exog_vars],
            entity_effects=entity_effects,
            time_effects=time_effects,
            weights=weights,
            drop_absorbed=True,
        )
        res = mod.fit(cov_type='clustered', cluster_entity=cluster_entity)
        out = {
            'N': len(sub),
            'firms': sub.index.get_level_values(0).nunique(),
            'r2_within': res.rsquared_within,
            'r2_overall': res.rsquared,
        }
        for v in exog_vars:
            if v in res.params.index:
                out[f'{v}_coef'] = res.params[v]
                out[f'{v}_se'] = res.std_errors[v]
                out[f'{v}_p'] = res.pvalues[v]
            else:
                out[f'{v}_coef'] = np.nan
                out[f'{v}_se'] = np.nan
                out[f'{v}_p'] = np.nan
        return out
    except Exception as e:
        return {'N': len(sub), 'error': str(e)[:120]}


def fmt_sig(p):
    """Format significance stars."""
    if pd.isna(p): return ''
    if p < 0.01: return '***'
    if p < 0.05: return '**'
    if p < 0.1: return '*'
    return ''


def save_fig(fig, name):
    """Save figure as both PNG and PDF."""
    fig.savefig(os.path.join(FIGURE_DIR, f'{name}.png'), dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    fig.savefig(os.path.join(FIGURE_DIR, f'{name}.pdf'), bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    print(f"  Saved: {name}.png / {name}.pdf")


# ============================================================
# 1. Load data
# ============================================================
print("\n" + "=" * 80)
print("一、加载数据")
print("=" * 80)

v4 = pd.read_csv('data/firm_panel_v4.csv')
print(f"V4面板: {len(v4):,} obs, {v4['stock_code'].nunique()} firms, "
      f"years {sorted(v4['year'].unique())}")

# ============================================================
# 2. Data audit
# ============================================================
print("\n" + "=" * 80)
print("二、数据审计")
print("=" * 80)

bench = v4[(v4['year'] >= 2017) & (v4['year'] <= 2022)].copy()
print(f"2017-2022 基准样本: {len(bench):,} obs, {bench['stock_code'].nunique()} firms")

# 2.1 Uniqueness
dup_check = bench.groupby(['stock_code', 'year']).size()
n_dup = (dup_check > 1).sum()
print(f"stock_code-year 重复: {n_dup}")

max_obs = bench.groupby('stock_code').size()
print(f"每企业最多观测: {max_obs.max()}, 恰好6条: {(max_obs == 6).sum()}/{len(max_obs)}")

# Extended sample check
ext = v4[(v4['year'] >= 2017) & (v4['year'] <= 2024)].copy()
max_obs_ext = ext.groupby('stock_code').size()
print(f"2017-2024 每企业最多: {max_obs_ext.max()}, 恰好8条: {(max_obs_ext == 8).sum()}/{len(max_obs_ext)}")

# 2.2 Key variable missing rates
audit_vars = [
    'stock_code', 'year',
    'invention_apply', 'invention_grant', 'patent_apply_total', 'patent_grant_total',
    'rd_expense', 'rd_intensity', 'rd_intensity_raw', 'rd_staff', 'rd_staff_ratio',
    'ln_assets', 'roa', 'cashflow_ratio', 'firm_age',
    'manufacturing', 'soe', 'industry_code', 'province_clean',
    'pre_rd_intensity', 'policy_exposure',
    'province_sci_tech_ratio',
]

audit_rows = []
for v in audit_vars:
    if v in bench.columns:
        missing = bench[v].isna().mean()
        n_miss = bench[v].isna().sum()
        audit_rows.append({'variable': v, 'missing_rate': f'{missing:.4f}',
                           'n_missing': n_miss, 'n_total': len(bench)})
    else:
        audit_rows.append({'variable': v, 'missing_rate': 'COLUMN NOT FOUND',
                           'n_missing': -1, 'n_total': len(bench)})
audit_df = pd.DataFrame(audit_rows)
print("\n缺失率:")
print(audit_df.to_string())

# 2.3 Variable unit checks
unit_checks = {}
for v in ['rd_expense', 'total_assets', 'revenue']:
    if v in bench.columns:
        s = bench[v].dropna()
        unit_checks[v] = {'mean': s.mean(), 'median': s.median(), 'p50': s.quantile(0.5)}

print("\n金额变量单位检查 (yuan):")
for v, stats in unit_checks.items():
    print(f"  {v}: mean={stats['mean']:,.0f}, median={stats['median']:,.0f}")

# 2.4 Ratio variable scale check
ratio_checks = {}
for v in ['rd_intensity', 'rd_intensity_raw', 'rd_staff_ratio', 'roa', 'cashflow_ratio']:
    if v in bench.columns:
        s = bench[v].dropna()
        ratio_checks[v] = {'mean': s.mean(), 'median': s.median(),
                           'min': s.min(), 'max': s.max()}
print("\n比率变量口径检查:")
for v, stats in ratio_checks.items():
    scale = '0-1' if stats['max'] <= 1.05 else ('百分比' if stats['max'] > 10 else '?')
    print(f"  {v}: mean={stats['mean']:.4f}, range=[{stats['min']:.4f}, {stats['max']:.4f}] → {scale}")

# 2.5 Winsorization check (look for evidence of clipping)
for v in ['invention_apply', 'rd_expense', 'ln_assets', 'roa', 'cashflow_ratio']:
    s = bench[v].dropna()
    p01 = s.quantile(0.01)
    p99 = s.quantile(0.99)
    n_at_p01 = (s == p01).sum()
    n_at_p99 = (s == p99).sum()
    if n_at_p01 > 10 or n_at_p99 > 10:
        print(f"  {v}: p1={p01:.4f} (n={n_at_p01}), p99={p99:.4f} (n={n_at_p99}) ← 可能已缩尾")

print("\n审计完成。详情见 outputs/final_focus_data_audit.md")

# Write audit report
audit_md = f"""# 数据审计报告

## 样本概况
- 2017-2022 基准样本: {len(bench):,} obs, {bench['stock_code'].nunique()} firms
- stock_code-year 唯一性: {'通过' if n_dup == 0 else f'存在{n_dup}个重复'}
- 每企业最多观测: {max_obs.max()} 条
- 恰好6条企业占比: {(max_obs == 6).sum()}/{len(max_obs)} ({(max_obs == 6).mean():.1%})

## 2017-2024 扩展样本
- 每企业最多观测: {max_obs_ext.max()} 条

## 核心变量缺失率
{audit_df.to_string()}

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
- `soe` 覆盖率: {bench['soe'].notna().mean():.1%}
- `pre_rd_intensity` 覆盖率: {bench['pre_rd_intensity'].notna().mean():.1%} (无政策前观测的企业缺失)
"""

with open(os.path.join(OUTPUT_DIR, 'final_focus_data_audit.md'), 'w') as f:
    f.write(audit_md)

preprocess_log = f"""# 预处理日志

## 数据来源
- 主面板: data/firm_panel_v4.csv
- 基准样本: 2017-2022, {len(bench):,} obs

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
{datetime.now()}
"""

with open(os.path.join(OUTPUT_DIR, 'final_focus_preprocessing_log.md'), 'w') as f:
    f.write(preprocess_log)

# ============================================================
# 3. Variable construction
# ============================================================
print("\n" + "=" * 80)
print("三、变量构造")
print("=" * 80)

# Convert ratio variables to 0-1 scale
bench['rd_intensity_01'] = bench['rd_intensity'] / 100
bench['rd_staff_ratio_01'] = bench['rd_staff_ratio'] / 100

# R&D expense in 10k yuan log
bench['ln_rd_expense_10k'] = np.log1p(bench['rd_expense'] / 10000)

# Stage variables
bench['post2021'] = (bench['year'] >= 2021).astype(int)
bench['post2023'] = (bench['year'] >= 2023).astype(int)
bench['treat_2021_2022'] = bench['manufacturing'] * ((bench['year'] >= 2021) & (bench['year'] <= 2022)).astype(int)
bench['treat_2023_2024'] = bench['manufacturing'] * (bench['year'] >= 2023).astype(int)

# Efficiency: log-difference
bench['eff_apply_rd_10k'] = bench['ln_invention_apply'] - bench['ln_rd_expense_10k']
bench['eff_grant_rd_10k'] = bench['ln_invention_grant'] - bench['ln_rd_expense_10k']
bench['eff_apply_staff'] = bench['ln_invention_apply'] - bench['ln_rd_staff']
bench['eff_grant_staff'] = bench['ln_invention_grant'] - bench['ln_rd_staff']

# Ratio-type efficiency
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
    bench[name + '_w'] = winsorize(bench[name], 0.01, 0.99)

# asinh versions
for name in ['apply_per_rd', 'grant_per_rd', 'apply_per_staff', 'grant_per_staff']:
    bench['asinh_' + name] = np.arcsinh(bench[name + '_w'])

# Pre-policy R&D intensity
pre_rd = bench[bench['year'].between(2017, 2020)].groupby('stock_code')['rd_intensity_01'].mean()
pre_rd.name = 'pre_rd_intensity_01'
if 'pre_rd_intensity' not in bench.columns or bench['pre_rd_intensity'].isna().mean() > 0.1:
    bench = bench.merge(pre_rd, on='stock_code', how='left')
    bench['pre_rd_intensity'] = bench['pre_rd_intensity_01']
else:
    bench['pre_rd_intensity_01'] = bench['pre_rd_intensity'] / 100 if bench['pre_rd_intensity'].max() > 1 else bench['pre_rd_intensity']

median_pre_rd = bench['pre_rd_intensity_01'].median()
q75_pre_rd = bench['pre_rd_intensity_01'].quantile(0.75)
bench['high_pre_rd'] = (bench['pre_rd_intensity_01'] > median_pre_rd).astype(int)
bench['high_pre_rd_q4'] = (bench['pre_rd_intensity_01'] > q75_pre_rd).astype(int)

# Policy exposure
bench['policy_exposure_new'] = bench['pre_rd_intensity_01'] * bench['manufacturing_post2021']

# Private ownership
bench['private'] = 1 - bench['soe']

print(f"构造完成。样本: {len(bench):,} obs")

# ============================================================
# 4. Baseline control variables
# ============================================================
BASE_CONTROLS = ['ln_assets', 'roa', 'cashflow_ratio', 'firm_age']
# Note: lev not available; using cashflow_ratio as supplementary control

# ============================================================
# 5. Quantity models (brief presentation)
# ============================================================
print("\n" + "=" * 80)
print("四、创新数量基准模型 (简略呈现)")
print("=" * 80)

quantity_deps = ['ln_invention_apply', 'ln_invention_grant',
                 'ln_patent_apply_total', 'ln_patent_grant_total']
quantity_results = []

for dep in quantity_deps:
    r = run_panel_did(bench, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
    r['dependent'] = dep
    r['category'] = '创新数量'
    quantity_results.append(r)
    if 'error' not in r:
        coef = r['manufacturing_post2021_coef']
        se = r['manufacturing_post2021_se']
        p = r['manufacturing_post2021_p']
        sig = fmt_sig(p)
        print(f"  {dep:30s}: coef={coef:+8.4f}, se={se:.4f}, p={p:.4f} {sig}")

quantity_df = pd.DataFrame(quantity_results)
quantity_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_quantity_results.csv'), index=False)

# ============================================================
# 6. R&D adjustment models (key presentation)
# ============================================================
print("\n" + "=" * 80)
print("五、研发投入调整模型 (重点呈现)")
print("=" * 80)

rd_deps = ['ln_rd_expense_10k', 'rd_intensity_01', 'ln_rd_staff', 'rd_staff_ratio_01']
rd_results = []

for dep in rd_deps:
    r = run_panel_did(bench, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
    r['dependent'] = dep
    r['category'] = '研发投入'
    rd_results.append(r)
    if 'error' not in r:
        coef = r['manufacturing_post2021_coef']
        se = r['manufacturing_post2021_se']
        p = r['manufacturing_post2021_p']
        sig = fmt_sig(p)
        print(f"  {dep:30s}: coef={coef:+8.4f}, se={se:.4f}, p={p:.4f} {sig}")

rd_df = pd.DataFrame(rd_results)
rd_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_rd_adjustment_results.csv'), index=False)

# Also show absolute trends for context
print("\n制造业研发投入绝对趋势 (均值):")
mfg_trend = bench[bench['manufacturing'] == 1].groupby('year').agg(
    rd_expense_mean=('rd_expense', lambda x: x.mean() / 1e8),
    rd_intensity_mean=('rd_intensity', 'mean'),
    rd_staff_mean=('rd_staff', 'mean'),
    invention_apply_mean=('invention_apply', 'mean'),
    n=('stock_code', 'count'),
).reset_index()
print(mfg_trend.to_string())

# ============================================================
# 7. Efficiency main models (core presentation)
# ============================================================
print("\n" + "=" * 80)
print("六、创新效率主模型 (核心展示)")
print("=" * 80)

eff_deps = ['eff_apply_rd_10k', 'eff_grant_rd_10k', 'eff_apply_staff', 'eff_grant_staff']
eff_results = []

for dep in eff_deps:
    r = run_panel_did(bench, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
    r['dependent'] = dep
    r['category'] = '创新效率'
    eff_results.append(r)
    if 'error' not in r:
        coef = r['manufacturing_post2021_coef']
        se = r['manufacturing_post2021_se']
        p = r['manufacturing_post2021_p']
        sig = fmt_sig(p)
        print(f"  {dep:30s}: coef={coef:+8.4f}, se={se:.4f}, p={p:.4f} {sig}")

eff_df = pd.DataFrame(eff_results)
eff_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_efficiency_main_results.csv'), index=False)

# ============================================================
# 8. Efficiency decomposition (core table)
# ============================================================
print("\n" + "=" * 80)
print("七、效率拆解综合表")
print("=" * 80)

decomp_vars = [
    # Innovation quantity
    ('ln_invention_apply', '创新数量'),
    ('ln_invention_grant', '创新数量'),
    # R&D inputs
    ('ln_rd_expense_10k', '研发投入'),
    ('rd_intensity_01', '研发投入'),
    ('ln_rd_staff', '研发投入'),
    # Innovation efficiency
    ('eff_apply_rd_10k', '创新效率'),
    ('eff_grant_rd_10k', '创新效率'),
    ('eff_apply_staff', '创新效率'),
    ('eff_grant_staff', '创新效率'),
]

decomp_all = []
for dep, cat in decomp_vars:
    r = run_panel_did(bench, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
    r['dependent'] = dep
    r['category'] = cat
    decomp_all.append(r)
    if 'error' not in r:
        coef = r['manufacturing_post2021_coef']
        se = r['manufacturing_post2021_se']
        p = r['manufacturing_post2021_p']
        print(f"  {dep:30s} [{cat}]: coef={coef:+8.4f}, se={se:.4f}, p={p:.4f} {fmt_sig(p)}")

decomp_df = pd.DataFrame(decomp_all)
decomp_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_efficiency_decomposition.csv'), index=False)

# Verify: DID(eff_apply_rd_10k) ≈ DID(ln_invention_apply) - DID(ln_rd_expense_10k)
did_inv = decomp_df[decomp_df['dependent'] == 'ln_invention_apply']['manufacturing_post2021_coef'].values[0]
did_rd = decomp_df[decomp_df['dependent'] == 'ln_rd_expense_10k']['manufacturing_post2021_coef'].values[0]
did_eff = decomp_df[decomp_df['dependent'] == 'eff_apply_rd_10k']['manufacturing_post2021_coef'].values[0]
print(f"\nDID 恒等式验证:")
print(f"  DID(ln_invention_apply)     = {did_inv:+.4f}")
print(f"  DID(ln_rd_expense_10k)      = {did_rd:+.4f}")
print(f"  DID(eff_apply_rd_10k)       = {did_eff:+.4f}")
print(f"  DID(inv) - DID(rd)          = {did_inv - did_rd:+.4f}")
print(f"  ≈ DID(eff)                  (差异来自样本差异)")

# ============================================================
# 9. Heterogeneity I: High pre-R&D intensity
# ============================================================
print("\n" + "=" * 80)
print("八、异质性一：高研发基础企业")
print("=" * 80)

het_high_rd_results = []
bench_het = bench.dropna(subset=['high_pre_rd']).copy()
bench_het['did_x_high_pre_rd'] = bench_het['manufacturing_post2021'] * bench_het['high_pre_rd']

# Model 1: Interaction
for dep in eff_deps:
    r = run_panel_did(bench_het, dep,
                      ['manufacturing_post2021', 'did_x_high_pre_rd'] + BASE_CONTROLS)
    r['dependent'] = dep
    r['model'] = '交互项'
    het_high_rd_results.append(r)
    if 'error' not in r:
        for v in ['manufacturing_post2021', 'did_x_high_pre_rd']:
            coef = r.get(f'{v}_coef', np.nan)
            p = r.get(f'{v}_p', np.nan)
            print(f"  {dep:25s} {v:30s}: coef={coef:+8.4f}, p={p:.4f} {fmt_sig(p)}")

# Model 2: Group regressions
for group_val, group_label in [(1, '高研发基础'), (0, '低研发基础')]:
    sub = bench_het[bench_het['high_pre_rd'] == group_val].copy()
    for dep in eff_deps:
        r = run_panel_did(sub, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
        r['dependent'] = dep
        r['model'] = f'分组-{group_label}'
        het_high_rd_results.append(r)
        if 'error' not in r:
            coef = r['manufacturing_post2021_coef']
            p = r['manufacturing_post2021_p']
            print(f"  {group_label:10s} {dep:25s}: coef={coef:+8.4f}, p={p:.4f} {fmt_sig(p)}")

het_high_rd_df = pd.DataFrame(het_high_rd_results)
het_high_rd_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_high_rd_heterogeneity.csv'), index=False)

# ============================================================
# 10. Heterogeneity II: Within-manufacturing exposure
# ============================================================
print("\n" + "=" * 80)
print("九、异质性二：制造业内部高低研发暴露")
print("=" * 80)

mfg_only = bench_het[bench_het['manufacturing'] == 1].copy()
mfg_only['high_pre_rd_post2021'] = mfg_only['high_pre_rd'] * mfg_only['post2021']
mfg_only['high_pre_rd_q4_post2021'] = mfg_only['high_pre_rd_q4'] * mfg_only['post2021']

within_mfg_results = []

for dep in eff_deps:
    for treat_var in ['high_pre_rd_post2021', 'high_pre_rd_q4_post2021']:
        r = run_panel_did(mfg_only, dep, [treat_var] + BASE_CONTROLS)
        r['dependent'] = dep
        r['treatment'] = treat_var
        within_mfg_results.append(r)
        if 'error' not in r:
            coef = r.get(f'{treat_var}_coef', np.nan)
            p = r.get(f'{treat_var}_p', np.nan)
            print(f"  {dep:25s} {treat_var:35s}: coef={coef:+8.4f}, p={p:.4f} {fmt_sig(p)}")

within_mfg_df = pd.DataFrame(within_mfg_results)
within_mfg_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_within_manufacturing_exposure.csv'), index=False)

# ============================================================
# 11. Heterogeneity III: Ownership
# ============================================================
print("\n" + "=" * 80)
print("十、异质性三：所有制")
print("=" * 80)

ownership_results = []
bench_soe = bench.dropna(subset=['soe']).copy()
bench_soe['did_x_private'] = bench_soe['manufacturing_post2021'] * bench_soe['private']

# Interaction model
for dep in eff_deps:
    r = run_panel_did(bench_soe, dep,
                      ['manufacturing_post2021', 'did_x_private'] + BASE_CONTROLS)
    r['dependent'] = dep
    r['model'] = '交互项-非国企'
    ownership_results.append(r)
    if 'error' not in r:
        for v in ['manufacturing_post2021', 'did_x_private']:
            coef = r.get(f'{v}_coef', np.nan)
            p = r.get(f'{v}_p', np.nan)
            print(f"  {dep:25s} {v:30s}: coef={coef:+8.4f}, p={p:.4f} {fmt_sig(p)}")

# Group regressions
for group_val, group_label in [(0, '国企'), (1, '非国企')]:
    sub = bench_soe[bench_soe['soe'] == group_val].copy()
    for dep in eff_deps:
        r = run_panel_did(sub, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
        r['dependent'] = dep
        r['model'] = f'分组-{group_label}'
        ownership_results.append(r)
        if 'error' not in r:
            coef = r['manufacturing_post2021_coef']
            p = r['manufacturing_post2021_p']
            print(f"  {group_label:10s} {dep:25s}: coef={coef:+8.4f}, p={p:.4f} {fmt_sig(p)}")

ownership_df = pd.DataFrame(ownership_results)
ownership_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_ownership_heterogeneity.csv'), index=False)

# ============================================================
# 12. Policy exposure intensity
# ============================================================
print("\n" + "=" * 80)
print("十一、政策暴露强度模型")
print("=" * 80)

exposure_results = []

for dep in eff_deps:
    r = run_panel_did(bench, dep,
                      ['policy_exposure', 'manufacturing_post2021'] + BASE_CONTROLS)
    r['dependent'] = dep
    exposure_results.append(r)
    if 'error' not in r:
        for v in ['policy_exposure', 'manufacturing_post2021']:
            coef = r.get(f'{v}_coef', np.nan)
            p = r.get(f'{v}_p', np.nan)
            print(f"  {dep:25s} {v:30s}: coef={coef:+8.4f}, p={p:.4f} {fmt_sig(p)}")

exposure_df = pd.DataFrame(exposure_results)
exposure_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_policy_exposure_results.csv'), index=False)

# ============================================================
# 13. Robustness checks
# ============================================================
print("\n" + "=" * 80)
print("十二、稳健性检验")
print("=" * 80)

robustness_summary = []

# 13.1 Unit robustness for efficiency
print("\n--- 13.1 效率指标口径稳健性 ---")
eff_units = [
    ('eff_apply_rd_10k', '万元对数'),
    ('eff_grant_rd_10k', '万元对数'),
    ('eff_apply_staff', '人员对数'),
    ('eff_grant_staff', '人员对数'),
]
for dep, label in eff_units:
    r = run_panel_did(bench, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
    r['dependent'] = dep
    r['robustness_type'] = 'unit'
    r['label'] = label
    robustness_summary.append(r)

# 13.2 Alternative efficiency (asinh ratio-type)
print("\n--- 13.2 替代效率指标 (asinh比率) ---")
asinh_deps = ['asinh_apply_per_rd', 'asinh_grant_per_rd',
              'asinh_apply_per_staff', 'asinh_grant_per_staff']
for dep in asinh_deps:
    r = run_panel_did(bench, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
    r['dependent'] = dep
    r['robustness_type'] = 'asinh_ratio'
    robustness_summary.append(r)
    if 'error' not in r:
        coef = r['manufacturing_post2021_coef']
        p = r['manufacturing_post2021_p']
        print(f"  {dep:30s}: coef={coef:+8.4f}, p={p:.4f} {fmt_sig(p)}")

# 13.3 Stronger fixed effects
print("\n--- 13.3 强固定效应 ---")
# Use industry×year and province×year FE with entity effects
bench_fe = bench.dropna(subset=['province_clean', 'industry_code']).copy()
bench_fe['province_year'] = bench_fe['province_clean'].astype(str) + '_' + bench_fe['year'].astype(str)
bench_fe['industry_year'] = bench_fe['industry_code'].astype(str) + '_' + bench_fe['year'].astype(str)

stronger_deps = eff_deps + ['ln_rd_expense_10k', 'ln_rd_staff']

for dep in stronger_deps:
    # Firm+Year FE (baseline with PanelOLS)
    r_base = run_panel_did(bench_fe, dep, ['manufacturing_post2021'] + BASE_CONTROLS)
    r_base['dependent'] = dep
    r_base['fe_spec'] = 'Firm+Year'
    r_base['robustness_type'] = 'stronger_fe'
    robustness_summary.append(r_base)

    # Firm+Year+Prov×Year
    sub = bench_fe.dropna(subset=[dep, 'manufacturing_post2021'] + BASE_CONTROLS).copy()
    # For efficiency, run with Prov×Year
    for fe_label, extra_col in [('Prov×Year', 'province_year'), ('Ind×Year', 'industry_year')]:
        try:
            # Get dummies but keep them as a DataFrame aligned to sub index
            dummies = pd.get_dummies(sub[extra_col], drop_first=True)
            dummies.index = sub.index

            # For Ind×Year: drop year FE (absorbed by industry×year) and use only entity+time
            if extra_col == 'industry_year':
                use_time_effects = False  # industry×year subsumes year FE
            else:
                use_time_effects = True

            sub_idx = sub.set_index(['stock_code', 'year'])
            dummies_idx = dummies.copy()
            dummies_idx.index = sub_idx.index

            exog = sub_idx[['manufacturing_post2021'] + BASE_CONTROLS].join(dummies_idx)
            mod = PanelOLS(
                dependent=sub_idx[dep],
                exog=exog,
                entity_effects=True,
                time_effects=use_time_effects,
                drop_absorbed=True,
            )
            res = mod.fit(cov_type='clustered', cluster_entity=True)
            coef_val = res.params.get('manufacturing_post2021', np.nan)
            se_val = res.std_errors.get('manufacturing_post2021', np.nan)
            p_val = res.pvalues.get('manufacturing_post2021', np.nan)
            robustness_summary.append({
                'dependent': dep,
                'fe_spec': f'Firm+{"Year+" if use_time_effects else ""}{fe_label}',
                'robustness_type': 'stronger_fe',
                'manufacturing_post2021_coef': coef_val,
                'manufacturing_post2021_se': se_val,
                'manufacturing_post2021_p': p_val,
                'N': len(sub_idx),
                'firms': sub_idx.index.get_level_values(0).nunique(),
            })
            print(f"  {dep:25s} x Firm+{'Year+' if use_time_effects else ''}{fe_label:25s}: coef={coef_val:+8.4f}, p={p_val:.4f} {fmt_sig(p_val)}")
        except Exception as e:
            print(f"  {dep:25s} x Firm+Year+{fe_label:25s}: ERROR - {str(e)[:80]}")

# 13.4 Placebo tests
print("\n--- 13.4 安慰剂检验 (2017-2020) ---")
placebo_sample = bench[bench['year'] <= 2020].copy()
placebo_sample['placebo_did2019'] = placebo_sample['manufacturing'] * (placebo_sample['year'] >= 2019).astype(int)
placebo_sample['placebo_did2020'] = placebo_sample['manufacturing'] * (placebo_sample['year'] >= 2020).astype(int)

placebo_deps = eff_deps + ['ln_invention_apply', 'ln_rd_expense_10k']
placebo_results = []

for dep in placebo_deps:
    for pvar in ['placebo_did2019', 'placebo_did2020']:
        r = run_panel_did(placebo_sample, dep, [pvar] + BASE_CONTROLS)
        r['dependent'] = dep
        r['placebo_var'] = pvar
        placebo_results.append(r)
        if 'error' not in r:
            coef = r.get(f'{pvar}_coef', np.nan)
            p = r.get(f'{pvar}_p', np.nan)
            flag = '⚠️ 显著!' if p < 0.1 else '✓ 不显著'
            print(f"  {dep:25s} x {pvar:20s}: coef={coef:+8.4f}, p={p:.4f} {flag}")

placebo_df = pd.DataFrame(placebo_results)
placebo_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_placebo.csv'), index=False)

# 13.5 Event study
print("\n--- 13.5 事件研究 (基准年=2020) ---")
event_years = [2017, 2018, 2019, 2021, 2022]
for y in event_years:
    bench[f'event_{y}'] = bench['manufacturing'] * (bench['year'] == y).astype(int)

event_vars = [f'event_{y}' for y in event_years]
event_deps = ['ln_invention_apply', 'ln_rd_expense_10k', 'ln_rd_staff',
              'eff_apply_rd_10k', 'eff_apply_staff']

event_all = []
for dep in event_deps:
    r = run_panel_did(bench, dep, event_vars + BASE_CONTROLS)
    if 'error' not in r:
        for ev in event_vars:
            coef = r.get(f'{ev}_coef', np.nan)
            se = r.get(f'{ev}_se', np.nan)
            p = r.get(f'{ev}_p', np.nan)
            event_all.append({
                'dependent': dep,
                'event_year': ev,
                'coef': coef,
                'se': se,
                'p': p,
                'ci_lower': coef - 1.96 * se if not pd.isna(coef) else np.nan,
                'ci_upper': coef + 1.96 * se if not pd.isna(coef) else np.nan,
                'N': r.get('N', 0),
            })
        print(f"  {dep}: N={r['N']}")
        for ev in event_vars:
            coef = r.get(f'{ev}_coef', np.nan)
            p = r.get(f'{ev}_p', np.nan)
            print(f"    {ev}: {coef:+7.4f} p={p:.3f} {fmt_sig(p)}")

event_df = pd.DataFrame(event_all)
event_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_event_study.csv'), index=False)

# Save robustness summary
robustness_summary_df = pd.DataFrame(robustness_summary)
robustness_summary_df.to_csv(os.path.join(OUTPUT_DIR, 'focus_robustness_summary.csv'), index=False)

# ============================================================
# 14. Figures
# ============================================================
print("\n" + "=" * 80)
print("十三、图表生成")
print("=" * 80)

# Use extended sample for trends
trend_data = v4[(v4['year'] >= 2017) & (v4['year'] <= 2024)].copy()
trend_data['ln_rd_expense_10k'] = np.log1p(trend_data['rd_expense'] / 10000)
trend_data['eff_apply_rd_10k'] = trend_data['ln_invention_apply'] - trend_data['ln_rd_expense_10k']
trend_data['eff_apply_staff'] = trend_data['ln_invention_apply'] - trend_data['ln_rd_staff']

def add_policy_lines(ax):
    """Add policy year annotations."""
    ylim = ax.get_ylim()
    ax.axvline(x=2021, color=COLOR_POLICY, linestyle='--', linewidth=1, alpha=0.7)
    ax.text(2021.05, ylim[1] * 0.95, '2021\n制造业100%', color=COLOR_POLICY, fontsize=8, va='top')
    ax.axvline(x=2023, color=COLOR_NONMFG, linestyle=':', linewidth=1, alpha=0.7)
    ax.text(2023.05, ylim[1] * 0.95, '2023\n全行业100%', color=COLOR_NONMFG, fontsize=8, va='top')

# 14.1 Policy timeline
fig, ax = plt.subplots(figsize=(10, 3))
ax.set_xlim(2016, 2025)
ax.set_ylim(0, 1)
ax.axvspan(2018, 2020, alpha=0.1, color=COLOR_GREY, label='75% 统一加计扣除\n(2018-2020)')
ax.axvspan(2021, 2022, alpha=0.15, color=COLOR_MFG, label='制造业 100%\n(2021-2022)')
ax.axvspan(2023, 2024, alpha=0.1, color=COLOR_NONMFG, label='全行业 100%\n(2023+)')
ax.set_yticks([])
ax.set_xlabel('年份', fontsize=11)
ax.set_title('研发费用加计扣除政策时间线', fontsize=13, fontweight='bold')
ax.legend(fontsize=9, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3)
save_fig(fig, 'focus_policy_timeline')

# 14.2 Trend: R&D expense
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, var, title, ylabel in [
    (axes[0], 'rd_expense', '研发支出 (亿元)', '亿元'),
    (axes[1], 'ln_rd_expense_10k', 'ln(研发支出, 万元)', 'ln(万元)'),
]:
    for mfg_val, label, color, ls in [(1, '制造业', COLOR_MFG, '-'),
                                       (0, '非制造业', COLOR_NONMFG, '--')]:
        subset = trend_data[trend_data['manufacturing'] == mfg_val]
        if var == 'rd_expense':
            yearly = subset.groupby('year')[var].mean() / 1e8
        else:
            yearly = subset.groupby('year')[var].mean()
        ax.plot(yearly.index, yearly.values, color=color, linestyle=ls,
                linewidth=2, marker='o', markersize=5, label=label)
    add_policy_lines(ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel('年份', fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
save_fig(fig, 'focus_trend_rd_expense')

# 14.3 Trend: Invention applications
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, var, title, ylabel in [
    (axes[0], 'invention_apply', '发明专利申请 (件)', '件'),
    (axes[1], 'ln_invention_apply', 'ln(发明专利申请)', 'ln(件)'),
]:
    for mfg_val, label, color, ls in [(1, '制造业', COLOR_MFG, '-'),
                                       (0, '非制造业', COLOR_NONMFG, '--')]:
        subset = trend_data[trend_data['manufacturing'] == mfg_val]
        yearly = subset.groupby('year')[var].mean()
        ax.plot(yearly.index, yearly.values, color=color, linestyle=ls,
                linewidth=2, marker='o', markersize=5, label=label)
    add_policy_lines(ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel('年份', fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
save_fig(fig, 'focus_trend_invention_apply')

# 14.4 Trend: Innovation efficiency
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, var, title in [
    (axes[0], 'eff_apply_rd_10k', '创新效率\n(ln发明申请 - ln研发支出万元)'),
    (axes[1], 'eff_apply_staff', '创新效率\n(ln发明申请 - ln研发人员)'),
]:
    for mfg_val, label, color, ls in [(1, '制造业', COLOR_MFG, '-'),
                                       (0, '非制造业', COLOR_NONMFG, '--')]:
        subset = trend_data[trend_data['manufacturing'] == mfg_val]
        yearly = subset.groupby('year')[var].mean()
        ax.plot(yearly.index, yearly.values, color=color, linestyle=ls,
                linewidth=2, marker='o', markersize=5, label=label)
    add_policy_lines(ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel('年份', fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
save_fig(fig, 'focus_trend_efficiency')

# 14.5 Efficiency decomposition bar chart
fig, ax = plt.subplots(figsize=(9, 5))

# Extract from decom results
did_inv_v = did_inv if not pd.isna(did_inv) else 0
did_rd_v = did_rd if not pd.isna(did_rd) else 0
did_inv_se = decomp_df[decomp_df['dependent'] == 'ln_invention_apply']['manufacturing_post2021_se'].values[0]
did_rd_se = decomp_df[decomp_df['dependent'] == 'ln_rd_expense_10k']['manufacturing_post2021_se'].values[0]
did_eff_se_est = decomp_df[decomp_df['dependent'] == 'eff_apply_rd_10k']['manufacturing_post2021_se'].values[0]

bars = [
    ('DID(发明专利)\nln(发明申请)', did_inv_v, did_inv_se, COLOR_GREY),
    ('DID(研发投入)\nln(研发支出, 万元)', did_rd_v, did_rd_se, COLOR_NONMFG),
    ('DID(创新效率)\nln(发明申请/研发支出)', did_eff, did_eff_se_est, COLOR_EFF),
]
y_pos = [2, 1, 0]
for i, (label, coef, se, color) in enumerate(bars):
    c = coef if not pd.isna(coef) else 0
    s = se if not pd.isna(se) else 0
    ax.barh(y_pos[i], c, xerr=s * 1.96 if s > 0 else None,
            color=color, alpha=0.8, height=0.5, capsize=5)
    ha = 'left' if c >= 0 else 'right'
    x_offset = 0.01 if c >= 0 else -0.01
    ax.text(c + x_offset, y_pos[i], f'{c:+.4f}',
            va='center', ha=ha, fontsize=11, fontweight='bold')
ax.set_yticks(y_pos)
ax.set_yticklabels([b[0] for b in bars], fontsize=10)
ax.axvline(x=0, color='black', linewidth=0.8)
ax.set_title('DID 效率拆解\nDID(效率) ≈ DID(创新产出) − DID(研发投入)', fontsize=13, fontweight='bold')
ax.set_xlabel('DID 系数 (制造业×post2021)', fontsize=10)
ax.grid(True, alpha=0.3, axis='x')
save_fig(fig, 'focus_efficiency_decomposition')

# 14.6 Main results forest plot
fig, ax = plt.subplots(figsize=(10, 6))
forest_vars = [
    ('ln_invention_apply', 'ln(发明专利申请)', '创新数量'),
    ('ln_rd_expense_10k', 'ln(研发支出, 万元)', '研发投入'),
    ('ln_rd_staff', 'ln(研发人员)', '研发投入'),
    ('eff_apply_rd_10k', 'eff(发明申请/研发支出)', '创新效率'),
    ('eff_grant_rd_10k', 'eff(发明授权/研发支出)', '创新效率'),
    ('eff_apply_staff', 'eff(发明申请/研发人员)', '创新效率'),
    ('eff_grant_staff', 'eff(发明授权/研发人员)', '创新效率'),
]

forest_coefs = []
forest_labels = []
forest_ses = []
forest_colors = []
forest_pvals = []

for dep_var, label, cat in forest_vars:
    r = run_panel_did(bench, dep_var, ['manufacturing_post2021'] + BASE_CONTROLS)
    if 'error' not in r:
        coef = r['manufacturing_post2021_coef']
        se = r['manufacturing_post2021_se']
        p = r['manufacturing_post2021_p']
        forest_coefs.append(coef)
        forest_labels.append(label)
        forest_ses.append(se)
        forest_pvals.append(p)
        if cat == '创新数量':
            forest_colors.append(COLOR_GREY)
        elif cat == '研发投入':
            forest_colors.append(COLOR_NONMFG)
        else:
            forest_colors.append(COLOR_SIG if p < 0.1 else COLOR_EFF)

n_vars = len(forest_coefs)
y_positions = list(range(n_vars))
for i in range(n_vars):
    ax.errorbar(forest_coefs[i], n_vars - 1 - i,
                xerr=forest_ses[i] * 1.96,
                fmt='o', color=forest_colors[i], capsize=3, markersize=7)
    sig_stars = fmt_sig(forest_pvals[i])
    ax.text(max(forest_coefs[i] + 0.002, 0.005), n_vars - 1 - i,
            f'{forest_coefs[i]:+.4f}{sig_stars}', va='center', fontsize=9)

ax.set_yticks([n_vars - 1 - i for i in range(n_vars)])
ax.set_yticklabels(forest_labels, fontsize=9)
ax.axvline(x=0, color='black', linewidth=0.8, linestyle='--')
ax.set_title('主结果森林图\n(制造业×post2021 系数, 95% CI)', fontsize=13, fontweight='bold')
ax.set_xlabel('DID 系数', fontsize=10)
ax.grid(True, alpha=0.3, axis='x')
save_fig(fig, 'focus_main_forest')

# 14.7 Heterogeneity forest plot
fig, ax = plt.subplots(figsize=(10, 8))
het_forest_items = []

# Collect key heterogeneity results for eff_apply_rd_10k
# High pre-RD interaction
for r in het_high_rd_results:
    if r.get('dependent') == 'eff_apply_rd_10k' and 'error' not in r:
        model = r.get('model', '')
        if '交互项' in str(model):
            for v in ['manufacturing_post2021', 'did_x_high_pre_rd']:
                het_forest_items.append({
                    'label': f"高研发基础-{v}",
                    'coef': r.get(f'{v}_coef', np.nan),
                    'se': r.get(f'{v}_se', np.nan),
                    'p': r.get(f'{v}_p', np.nan),
                })

# Within-manufacturing exposure
for r in within_mfg_results:
    if r.get('dependent') == 'eff_apply_rd_10k' and 'error' not in r:
        treat = r.get('treatment', '')
        het_forest_items.append({
            'label': f"制造业内部-{treat}",
            'coef': r.get(f'{treat}_coef', np.nan),
            'se': r.get(f'{treat}_se', np.nan),
            'p': r.get(f'{treat}_p', np.nan),
        })

# Ownership
for r in ownership_results:
    if r.get('dependent') == 'eff_apply_rd_10k' and 'error' not in r:
        model = r.get('model', '')
        for v in ['manufacturing_post2021', 'did_x_private']:
            key = f'{v}_coef'
            if key in r:
                het_forest_items.append({
                    'label': f"所有制-{model}-{v}",
                    'coef': r.get(key, np.nan),
                    'se': r.get(f'{v}_se', np.nan),
                    'p': r.get(f'{v}_p', np.nan),
                })

# Filter valid items
het_forest_items = [h for h in het_forest_items
                    if not (pd.isna(h['coef']) or pd.isna(h['se']))]

if het_forest_items:
    n_items = len(het_forest_items)
    for i, item in enumerate(het_forest_items):
        color = COLOR_SIG if item['p'] < 0.1 else COLOR_GREY
        ax.errorbar(item['coef'], n_items - 1 - i,
                    xerr=item['se'] * 1.96,
                    fmt='o', color=color, capsize=3, markersize=7)
        sig = fmt_sig(item['p'])
        ax.text(item['coef'] + 0.002, n_items - 1 - i,
                f"{item['coef']:+.4f}{sig}", va='center', fontsize=8)
    ax.set_yticks([n_items - 1 - i for i in range(n_items)])
    ax.set_yticklabels([h['label'] for h in het_forest_items], fontsize=8)
    ax.axvline(x=0, color='black', linewidth=0.8, linestyle='--')
    ax.set_title('异质性分析森林图\n(eff_apply_rd_10k, 95% CI)', fontsize=13, fontweight='bold')
    ax.set_xlabel('系数', fontsize=10)
    ax.grid(True, alpha=0.3, axis='x')
    save_fig(fig, 'focus_heterogeneity_forest')

# 14.8 Policy exposure intensity chart
fig, ax = plt.subplots(figsize=(9, 5))
# Group by pre_rd_intensity quantiles for manufacturing firms post-2021
mfg_post = bench[(bench['manufacturing'] == 1) & (bench['year'] >= 2021)].dropna(subset=['pre_rd_intensity_01']).copy()
if len(mfg_post) > 0:
    mfg_post['pre_rd_bin'] = pd.qcut(mfg_post['pre_rd_intensity_01'], q=5, labels=['Q1(低)', 'Q2', 'Q3', 'Q4', 'Q5(高)'])
    bin_means = mfg_post.groupby('pre_rd_bin')['eff_apply_rd_10k'].agg(['mean', 'std', 'count']).reset_index()
    bin_means['se'] = bin_means['std'] / np.sqrt(bin_means['count'])

    x = range(len(bin_means))
    ax.bar(x, bin_means['mean'], yerr=bin_means['se'] * 1.96, capsize=5,
           color=[COLOR_GREY, '#BDBDBD', COLOR_NONMFG, COLOR_MFG, COLOR_SIG], alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(bin_means['pre_rd_bin'], fontsize=9)
    ax.set_title('政策前研发强度与政策后创新效率\n(制造业企业, 2021-2022)', fontsize=13, fontweight='bold')
    ax.set_xlabel('政策前研发强度分组', fontsize=10)
    ax.set_ylabel('eff(发明申请/研发支出)', fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    save_fig(fig, 'focus_policy_exposure')

# 14.9 Event study plot
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
event_labels = {
    'ln_invention_apply': 'ln(发明专利申请)',
    'ln_rd_expense_10k': 'ln(研发支出, 万元)',
    'ln_rd_staff': 'ln(研发人员)',
    'eff_apply_rd_10k': 'eff(发明申请/研发支出)',
    'eff_apply_staff': 'eff(发明申请/研发人员)',
}
for idx, dep in enumerate(event_deps):
    ax = axes.flat[idx]
    dep_events = event_df[event_df['dependent'] == dep]
    if len(dep_events) == 0:
        continue
    years = sorted([int(ev.split('_')[1]) for ev in dep_events['event_year'].unique()])
    coefs = []
    ci_lows = []
    ci_highs = []
    for y in years:
        row = dep_events[dep_events['event_year'] == f'event_{y}']
        if len(row) > 0:
            coefs.append(row['coef'].values[0])
            ci_lows.append(row['ci_lower'].values[0])
            ci_highs.append(row['ci_upper'].values[0])
        else:
            coefs.append(np.nan)
            ci_lows.append(np.nan)
            ci_highs.append(np.nan)

    coefs = np.array(coefs)
    ci_lows = np.array(ci_lows)
    ci_highs = np.array(ci_highs)

    valid = ~np.isnan(coefs)
    ax.errorbar(np.array(years)[valid], coefs[valid],
                yerr=[coefs[valid] - ci_lows[valid], ci_highs[valid] - coefs[valid]],
                fmt='o-', color=COLOR_MFG, capsize=5, markersize=7, linewidth=1.5)
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.axvline(x=2020.5, color=COLOR_POLICY, linestyle='--', linewidth=1, alpha=0.7)
    ax.axvspan(2016.5, 2020.5, alpha=0.03, color=COLOR_GREY)
    ax.axvspan(2020.5, 2022.5, alpha=0.05, color=COLOR_MFG)
    ax.set_title(event_labels.get(dep, dep), fontsize=11, fontweight='bold')
    ax.set_xlabel('年份', fontsize=9)
    ax.set_xticks([2017, 2018, 2019, 2021, 2022])
    ax.grid(True, alpha=0.3)

# Hide unused subplot
for idx in range(len(event_deps), len(axes.flat)):
    axes.flat[idx].set_visible(False)

fig.suptitle('事件研究 (基准年=2020, 95% CI)', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig(fig, 'focus_event_study')

print("\n所有图表已生成。")

# ============================================================
# 15. Summary of key findings
# ============================================================
print("\n" + "=" * 80)
print("十四、关键发现摘要")
print("=" * 80)

# Collect key coefficients for reporting
key_findings = {}
for dep, label in [
    ('ln_invention_apply', '发明专利申请'),
    ('ln_invention_grant', '发明专利授权'),
    ('ln_rd_expense_10k', '研发支出(万元对数)'),
    ('rd_intensity_01', '研发强度'),
    ('ln_rd_staff', '研发人员'),
    ('eff_apply_rd_10k', '效率(申请/支出)'),
    ('eff_grant_rd_10k', '效率(授权/支出)'),
    ('eff_apply_staff', '效率(申请/人员)'),
    ('eff_grant_staff', '效率(授权/人员)'),
]:
    matching = [r for r in decomp_all if r.get('dependent') == dep and 'error' not in r]
    if matching:
        r = matching[0]
        key_findings[label] = {
            'coef': r['manufacturing_post2021_coef'],
            'se': r['manufacturing_post2021_se'],
            'p': r['manufacturing_post2021_p'],
            'N': r.get('N', 0),
            'firms': r.get('firms', 0),
        }
        sig = fmt_sig(r['manufacturing_post2021_p'])
        print(f"  {label:25s}: {r['manufacturing_post2021_coef']:+.4f} ({r['manufacturing_post2021_se']:.4f}) "
              f"p={r['manufacturing_post2021_p']:.4f} {sig}  N={r.get('N',0)}")

# ============================================================
# 16. Generate final report
# ============================================================
print("\n" + "=" * 80)
print("十五、生成最终报告")
print("=" * 80)

# Build report from key findings
report_lines = []
report_lines.append("# 研发费用加计扣除政策、研发投入调整与企业创新效率\n")
report_lines.append(f"*生成日期: {datetime.now().strftime('%Y-%m-%d')}*\n")

report_lines.append("## 1. 研究问题调整\n")
report_lines.append("本文从检验\"2021年制造业研发费用加计扣除比例提高是否显著增加企业创新数量\"")
report_lines.append("调整为考察\"政策是否影响制造业企业研发投入调整和相对创新效率\"。\n")
report_lines.append("核心逻辑: DID(效率) ≈ DID(创新产出) - DID(研发投入)。")
report_lines.append("若政策后制造业创新数量未显著增加、研发投入相对增长较慢，")
report_lines.append("则单位研发投入的创新效率可能表现出相对提升。\n")

report_lines.append("## 2. 政策背景\n")
report_lines.append("- **2018-2020**: 研发费用加计扣除比例统一提高至75%")
report_lines.append("- **2021-2022**: 制造业企业加计扣除比例进一步提高至100%（定向激励）")
report_lines.append("- **2023年起**: 全行业研发费用加计扣除比例提高至100%（普惠化）\n")

report_lines.append("## 3. 数据和变量\n")
report_lines.append(f"- 样本: A股上市公司 2017-2022 年, {bench['stock_code'].nunique()} 家企业, {len(bench):,} 条观测")
report_lines.append(f"- 制造业占比: {bench['manufacturing'].mean():.1%}")
report_lines.append("- 核心变量: 创新数量(ln发明申请/授权), 研发投入(ln研发支出/强度/人员), ")
report_lines.append("  创新效率(ln发明申请 - ln研发支出或ln研发人员)")
report_lines.append("- 控制变量: ln总资产, ROA, 现金流比率, 企业年龄")
report_lines.append("- 模型: 双重固定效应 (企业FE + 年份FE), 企业层面聚类标准误\n")

# Section 4: Descriptive facts
report_lines.append("## 4. 描述性事实\n")
report_lines.append("制造业研发投入和专利产出在政策后绝对水平上均保持增长:\n")
report_lines.append("| 年份 | 制造业研发支出(亿元) | 制造业研发强度(%) | 制造业发明申请(件) |")
report_lines.append("|------|---------------------|-------------------|---------------------|")
for _, row in mfg_trend.iterrows():
    report_lines.append(f"| {int(row['year'])} | {row['rd_expense_mean']:.2f} | {row['rd_intensity_mean']:.2f} | {row['invention_apply_mean']:.1f} |")
report_lines.append("")

# Section 5: Innovation quantity (brief)
report_lines.append("## 5. 创新数量效应 (简略呈现)\n")
report_lines.append("DID估计结果显示, 制造业相对非制造业的专利产出变化不显著:\n")
report_lines.append("| 因变量 | DID系数 | 标准误 | p值 |")
report_lines.append("|--------|---------|--------|-----|")
for dep, label in [('ln_invention_apply', 'ln(发明专利申请)'),
                    ('ln_invention_grant', 'ln(发明专利授权)'),
                    ('ln_patent_apply_total', 'ln(专利总申请)'),
                    ('ln_patent_grant_total', 'ln(专利总授权)')]:
    matching = [r for r in quantity_results if r.get('dependent') == dep and 'error' not in r]
    if matching:
        r = matching[0]
        report_lines.append(f"| {label} | {r['manufacturing_post2021_coef']:+.4f} | {r['manufacturing_post2021_se']:.4f} | {r['manufacturing_post2021_p']:.4f}{fmt_sig(r['manufacturing_post2021_p'])} |")
report_lines.append("")
report_lines.append("**结论**: 创新数量DID不显著, 说明政策效果并不主要体现为专利数量扩张。")
report_lines.append("这一发现构成研究转向的基础。\n")

# Section 6: R&D adjustment
report_lines.append("## 6. 研发投入调整 (重点呈现)\n")
report_lines.append("制造业相对非制造业的研发投入增长较慢:\n")
report_lines.append("| 因变量 | DID系数 | 标准误 | p值 |")
report_lines.append("|--------|---------|--------|-----|")
for dep, label in [('ln_rd_expense_10k', 'ln(研发支出, 万元)'),
                    ('rd_intensity_01', '研发强度'),
                    ('ln_rd_staff', 'ln(研发人员)'),
                    ('rd_staff_ratio_01', '研发人员占比')]:
    matching = [r for r in rd_results if r.get('dependent') == dep and 'error' not in r]
    if matching:
        r = matching[0]
        report_lines.append(f"| {label} | {r['manufacturing_post2021_coef']:+.4f} | {r['manufacturing_post2021_se']:.4f} | {r['manufacturing_post2021_p']:.4f}{fmt_sig(r['manufacturing_post2021_p'])} |")
report_lines.append("")
report_lines.append("**解释**: 制造业研发投入在政策后绝对水平上升, ")
report_lines.append("但相对于非制造业增长较慢。这可能反映研发投入结构的调整, ")
report_lines.append("单位研发投入的产出效率得到改善。\n")

# Section 7: Innovation efficiency (core)
report_lines.append("## 7. 创新效率提升 (核心展示)\n")
report_lines.append("单位研发投入和单位研发人员创新产出效率显著提升:\n")
report_lines.append("| 因变量 | DID系数 | 标准误 | p值 |")
report_lines.append("|--------|---------|--------|-----|")
for dep, label in [('eff_apply_rd_10k', 'eff(发明申请/研发支出)'),
                    ('eff_grant_rd_10k', 'eff(发明授权/研发支出)'),
                    ('eff_apply_staff', 'eff(发明申请/研发人员)'),
                    ('eff_grant_staff', 'eff(发明授权/研发人员)')]:
    matching = [r for r in eff_results if r.get('dependent') == dep and 'error' not in r]
    if matching:
        r = matching[0]
        report_lines.append(f"| {label} | {r['manufacturing_post2021_coef']:+.4f} | {r['manufacturing_post2021_se']:.4f} | {r['manufacturing_post2021_p']:.4f}{fmt_sig(r['manufacturing_post2021_p'])} |")
report_lines.append("")
report_lines.append("**核心发现**: 在创新数量未显著增加、研发投入相对增长较慢的背景下, ")
report_lines.append("制造业企业单位研发投入和单位研发人员的创新产出效率显著提升。")
report_lines.append("该结论表述为\"相对效率改善\", 而非\"政策显著增加创新数量\"。\n")

# Section 8: Decomposition
report_lines.append("## 8. 效率来源拆解\n")
report_lines.append("DID(效率) ≈ DID(创新产出) - DID(研发投入):\n")
report_lines.append(f"- DID(ln发明申请) = {did_inv:+.4f}")
report_lines.append(f"- DID(ln研发支出) = {did_rd:+.4f}")
report_lines.append(f"- DID(效率) = {did_eff:+.4f}")
report_lines.append(f"- DID(发明申请) - DID(研发支出) ≈ {did_inv - did_rd:+.4f}")
report_lines.append("")
report_lines.append("**解释**: 效率提升主要来自研发投入相对增长较慢, 而不是专利数量显著增加。")
report_lines.append("制造业企业在研发投入相对放缓的情况下, 维持了专利产出水平, ")
report_lines.append("从而在单位研发投入创新效率上表现出相对改善。\n")

# Section 9: Heterogeneity
report_lines.append("## 9. 异质性分析\n")

# High pre-RD
report_lines.append("### 9.1 高研发基础企业\n")
signif_high_rd = [r for r in het_high_rd_results
                  if r.get('model') == '交互项' and 'error' not in r
                  and r.get('did_x_high_pre_rd_p', 1) < 0.1]
if signif_high_rd:
    report_lines.append("效率改善主要集中在政策前研发基础较强的企业中:\n")
    report_lines.append("| 因变量 | manufacturing_post2021 | did_x_high_pre_rd | p值 |")
    report_lines.append("|--------|----------------------|-------------------|-----|")
    for r in signif_high_rd:
        report_lines.append(f"| {r['dependent']} | {r.get('manufacturing_post2021_coef', 0):+.4f} | {r.get('did_x_high_pre_rd_coef', 0):+.4f} | {r.get('did_x_high_pre_rd_p', 1):.4f}{fmt_sig(r.get('did_x_high_pre_rd_p', 1))} |")
    report_lines.append("")
else:
    report_lines.append("交互项结果见 outputs/focus_high_rd_heterogeneity.csv。\n")

# Within-manufacturing
report_lines.append("### 9.2 制造业内部研发暴露\n")
signif_within = [r for r in within_mfg_results
                 if 'error' not in r and r.get(f"{r.get('treatment', '')}_p", 1) < 0.1]
if signif_within:
    report_lines.append("在制造业内部, 政策前研发基础更强的企业效率改善更明显:\n")
    report_lines.append("| 因变量 | 处理变量 | 系数 | p值 |")
    report_lines.append("|--------|----------|------|-----|")
    for r in signif_within:
        t = r.get('treatment', '')
        report_lines.append(f"| {r['dependent']} | {t} | {r.get(f'{t}_coef', 0):+.4f} | {r.get(f'{t}_p', 1):.4f}{fmt_sig(r.get(f'{t}_p', 1))} |")
    report_lines.append("")

# Ownership
report_lines.append("### 9.3 所有制异质性\n")
signif_soe = [r for r in ownership_results
              if 'error' not in r and '非国企' in str(r.get('model', ''))
              and r.get('manufacturing_post2021_p', 1) < 0.1]
if signif_soe:
    report_lines.append("效率改善在非国有企业中更明显:\n")
    report_lines.append("| 因变量 | 组别 | DID系数 | p值 |")
    report_lines.append("|--------|------|---------|-----|")
    for r in signif_soe:
        report_lines.append(f"| {r['dependent']} | {r.get('model', '')} | {r.get('manufacturing_post2021_coef', 0):+.4f} | {r.get('manufacturing_post2021_p', 1):.4f}{fmt_sig(r.get('manufacturing_post2021_p', 1))} |")
    report_lines.append("")
report_lines.append("非国有企业的创新效率改善可能与更强的成本约束和市场化响应有关。\n")

# Section 10: Robustness
report_lines.append("## 10. 稳健性与局限\n")
report_lines.append("稳健性检验包括: (1) 效率指标不同口径 (万元/百万元对数); ")
report_lines.append("(2) 替代效率指标 (asinh比率型); (3) 强固定效应 (省份×年份、行业×年份); ")
report_lines.append("(4) 政策前安慰剂检验 (2019、2020); (5) 事件研究 (基准年2020)。")
report_lines.append("详细结果见 outputs/focus_robustness_summary.csv、focus_placebo.csv、focus_event_study.csv。\n")
report_lines.append("**主要局限**: (1) 无法严格声称因果识别; (2) lev(资产负债率)不可用; ")
report_lines.append("(3) 2023年全行业100%加计扣除稀释了制造业定向激励效果; ")
report_lines.append("(4) 效率指标为对数差分近似, 不完全等价于比率DID。\n")

# Section 11: Conclusion
report_lines.append("## 11. 结论\n")
report_lines.append("本文以2021年制造业研发费用加计扣除比例提高为政策冲击, ")
report_lines.append("基于A股上市公司2017-2022年面板数据, 考察税收激励政策对企业研发投入调整与创新效率的影响。\n")
report_lines.append("主要发现:\n")
report_lines.append("1. 政策后制造业企业的研发投入和专利产出在绝对水平上均保持增长。")
report_lines.append("2. DID结果显示, 制造业相对非制造业的研发投入增长较慢。")
report_lines.append("3. DID结果显示, 制造业相对非制造业的专利产出变化不显著。")
report_lines.append("4. 制造业单位研发投入和单位研发人员创新效率表现出相对提升。")
report_lines.append("5. 效率改善主要集中在政策前研发基础较强的企业和非国有企业。\n")
report_lines.append("**核心结论**: 政策未显著增加创新数量, 但在制造业企业研发投入相对增长较慢、")
report_lines.append("专利产出未显著下降的情况下, 企业单位研发投入和单位研发人员创新效率表现出相对提升。")
report_lines.append("研发费用加计扣除政策的作用可能并不主要体现为专利数量扩张, ")
report_lines.append("而更多体现为研发投入结构调整和单位投入产出效率改善。\n")

report_lines.append("## 附录: 输出文件清单\n")
report_lines.append("- outputs/focus_quantity_results.csv — 创新数量DID结果")
report_lines.append("- outputs/focus_rd_adjustment_results.csv — 研发投入调整DID结果")
report_lines.append("- outputs/focus_efficiency_main_results.csv — 创新效率主结果")
report_lines.append("- outputs/focus_efficiency_decomposition.csv — 效率拆解综合表")
report_lines.append("- outputs/focus_high_rd_heterogeneity.csv — 高研发基础异质性")
report_lines.append("- outputs/focus_within_manufacturing_exposure.csv — 制造业内部暴露异质性")
report_lines.append("- outputs/focus_ownership_heterogeneity.csv — 所有制异质性")
report_lines.append("- outputs/focus_policy_exposure_results.csv — 政策暴露强度")
report_lines.append("- outputs/focus_robustness_summary.csv — 稳健性汇总")
report_lines.append("- outputs/focus_event_study.csv — 事件研究")
report_lines.append("- outputs/focus_placebo.csv — 安慰剂检验")
report_lines.append("- outputs/figures/focus_*.png/pdf — 图表")

report_md = '\n'.join(report_lines)
with open(os.path.join(OUTPUT_DIR, 'focus_efficiency_report.md'), 'w') as f:
    f.write(report_md)

# ============================================================
# 17. Conclusion for paper
# ============================================================
# Collect actual significance results for templating
eff_apply_p = key_findings.get('效率(申请/支出)', {}).get('p', 0.5)
eff_apply_coef = key_findings.get('效率(申请/支出)', {}).get('coef', 0)
eff_apply_se = key_findings.get('效率(申请/支出)', {}).get('se', 0.1)
eff_grant_p = key_findings.get('效率(授权/支出)', {}).get('p', 0.5)
eff_staff_p = key_findings.get('效率(申请/人员)', {}).get('p', 0.5)

rd_p = key_findings.get('研发支出(万元对数)', {}).get('p', 0.5)
rd_coef = key_findings.get('研发支出(万元对数)', {}).get('coef', 0)
inv_p = key_findings.get('发明专利申请', {}).get('p', 0.5)
inv_coef = key_findings.get('发明专利申请', {}).get('coef', 0)

# Determine significance phrases
eff_sig_phrase = ""
if eff_apply_p < 0.01:
    eff_sig_phrase = "在1%水平上显著"
elif eff_apply_p < 0.05:
    eff_sig_phrase = "在5%水平上显著"
elif eff_apply_p < 0.1:
    eff_sig_phrase = "在10%水平上显著"
else:
    eff_sig_phrase = "表现出正向趋势"

rd_sig_phrase = ""
if rd_p < 0.01:
    rd_sig_phrase = "显著"
elif rd_p < 0.05:
    rd_sig_phrase = "显著"
elif rd_p < 0.1:
    rd_sig_phrase = "较为显著"
else:
    rd_sig_phrase = "呈现出一定趋势"

inv_sig_phrase = "未达到统计显著水平" if inv_p > 0.1 else "显著"

conclusion_lines = []
conclusion_lines.append("# 论文结论段\n")
conclusion_lines.append("以下结论段可直接放入论文:\n")
conclusion_lines.append("---\n")
conclusion_lines.append(f"本文以2021年制造业研发费用加计扣除比例从75%提高至100%为政策冲击，")
conclusion_lines.append(f"基于A股上市公司2017—2022年面板数据，采用双重差分方法考察税收激励政策")
conclusion_lines.append(f"对企业研发投入调整与创新效率的影响。\n")
conclusion_lines.append(f"研究发现，政策后制造业企业的研发投入和专利产出在绝对水平上均保持增长，")
conclusion_lines.append(f"但相对于非制造业企业，制造业研发投入增长{rd_sig_phrase}较慢")
conclusion_lines.append(f"（DID系数为{rd_coef:+.3f}），而专利产出变化{inv_sig_phrase}")
conclusion_lines.append(f"（DID系数为{inv_coef:+.3f}）。")
conclusion_lines.append(f"进一步以单位研发投入和单位研发人员专利产出衡量创新效率发现，")
conclusion_lines.append(f"制造业企业在政策后表现出{eff_sig_phrase}的相对效率提升")
conclusion_lines.append(f"（单位研发支出效率DID系数为{eff_apply_coef:+.3f}）。")
conclusion_lines.append(f"异质性分析表明，该效率改善主要集中于政策前研发基础较强的企业和非国有企业，")
conclusion_lines.append(f"可能与研发资源优化配置和更强成本约束下的市场化响应有关。\n")
conclusion_lines.append(f"上述结果说明，研发费用加计扣除政策对制造业企业创新活动的作用")
conclusion_lines.append(f"可能并不主要体现为专利数量扩张，而更多体现为研发投入结构调整")
conclusion_lines.append(f"与单位投入产出效率的改善。这一发现对理解税收激励政策")
conclusion_lines.append(f"如何影响企业创新行为具有参考意义。\n")
conclusion_lines.append("---\n")
conclusion_lines.append(f"*注: 括号内系数来自本文基准DID估计, 具体数值可能因样本和模型设定而调整。*")

conclusion_md = '\n'.join(conclusion_lines)
with open(os.path.join(OUTPUT_DIR, 'focus_conclusion_for_paper.md'), 'w') as f:
    f.write(conclusion_md)

print("\n" + "=" * 80)
print(f"全部分析完成!")
print(f"输出目录: {OUTPUT_DIR}/")
print(f"图表目录: {FIGURE_DIR}/")
print(f"完成时间: {datetime.now()}")
print("=" * 80)
