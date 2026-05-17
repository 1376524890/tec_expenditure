#!/usr/bin/env python3
"""
Generate all 12 figures for the revised paper.
Output: outputs/figures_revised/
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import FancyBboxPatch
import os
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = 'outputs/figures_revised'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# Font & style defaults
# ============================================================
matplotlib.rcParams['figure.dpi'] = 300
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['savefig.bbox'] = 'tight'
matplotlib.rcParams['figure.facecolor'] = 'white'
matplotlib.rcParams['axes.facecolor'] = 'white'
matplotlib.rcParams['font.size'] = 10
matplotlib.rcParams['axes.titlesize'] = 12
matplotlib.rcParams['axes.labelsize'] = 10
matplotlib.rcParams['legend.fontsize'] = 8
matplotlib.rcParams['xtick.labelsize'] = 8
matplotlib.rcParams['ytick.labelsize'] = 8

try:
    matplotlib.rcParams['font.family'] = 'Noto Sans CJK SC'
except:
    try:
        matplotlib.rcParams['font.family'] = 'WenQuanYi Micro Hei'
    except:
        pass
matplotlib.rcParams['axes.unicode_minus'] = False

# Grayscale-friendly palette
C_MFG      = '#404040'   # dark gray for manufacturing
C_NONMFG   = '#808080'   # medium gray for non-manufacturing
C_POLICY   = '#000000'   # black for policy line
C_EFF      = '#505050'   # dark gray for efficiency
C_SIG_POS  = '#333333'   # significant positive
C_SIG_NEG  = '#555555'   # significant negative
C_NS       = '#B0B0B0'   # non-significant (light gray)
C_HATCH1   = '///'
C_HATCH2   = '\\\\\\'
MARKER_MFG = 's'
MARKER_NONMFG = 'o'

def save_fig(fig, name):
    fig.savefig(os.path.join(OUTPUT_DIR, f'{name}.png'), dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    fig.savefig(os.path.join(OUTPUT_DIR, f'{name}.pdf'), bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    print(f'  Saved: {name}.png / {name}.pdf')


def fmt_sig(p):
    if pd.isna(p): return ''
    if p < 0.01: return '***'
    if p < 0.05: return '**'
    if p < 0.1: return '*'
    return ''


# ============================================================
# Load data
# ============================================================
v4 = pd.read_csv('data/firm_panel_v4.csv')
bench = v4[(v4['year'] >= 2017) & (v4['year'] <= 2022)].copy()

# Variable construction
bench['rd_intensity_01'] = bench['rd_intensity'] / 100
bench['rd_staff_ratio_01'] = bench['rd_staff_ratio'] / 100
bench['ln_rd_expense_10k'] = np.log1p(bench['rd_expense'] / 10000)
bench['post2021'] = (bench['year'] >= 2021).astype(int)
bench['eff_apply_rd_10k'] = bench['ln_invention_apply'] - bench['ln_rd_expense_10k']
bench['eff_grant_rd_10k'] = bench['ln_invention_grant'] - bench['ln_rd_expense_10k']
bench['eff_apply_staff'] = bench['ln_invention_apply'] - bench['ln_rd_staff']
bench['eff_grant_staff'] = bench['ln_invention_grant'] - bench['ln_rd_staff']

# ============================================================
# Figure 1: Sample structure
# ============================================================
print('Generating Figure 1: Sample structure...')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

# Pie chart
sizes = [16740, 26772-16740]
labels = ['制造业\n(16,740条, 62.5%)', '非制造业\n(10,032条, 37.5%)']
colors = [C_MFG, C_NONMFG]
wedges, texts = ax1.pie(sizes, labels=None, colors=colors, startangle=90,
                          wedgeprops={'edgecolor': 'white', 'linewidth': 1})
ax1.legend(wedges, labels, loc='lower center', fontsize=9, frameon=False)
ax1.set_title('样本结构', fontsize=12, fontweight='bold')

# Bar: by year
yearly_mfg = bench.groupby('year')['manufacturing'].agg(['sum', 'count']).reset_index()
yearly_mfg['mfg_pct'] = yearly_mfg['sum'] / yearly_mfg['count'] * 100
yearly_mfg['nonmfg'] = yearly_mfg['count'] - yearly_mfg['sum']

x = yearly_mfg['year'].values
ax2.bar(x, yearly_mfg['nonmfg'], color=C_NONMFG, label='非制造业', edgecolor='white')
ax2.bar(x, yearly_mfg['sum'], bottom=yearly_mfg['nonmfg'], color=C_MFG,
        label='制造业', edgecolor='white')
for i, yr in enumerate(x):
    ax2.text(yr, yearly_mfg['count'].values[i] + 100,
             f"{yearly_mfg['mfg_pct'].values[i]:.1f}%", ha='center', fontsize=7, fontweight='bold')
ax2.set_title('分年度样本构成', fontsize=12, fontweight='bold')
ax2.set_xlabel('年份')
ax2.set_ylabel('观测数')
ax2.legend(fontsize=9, frameon=False)
ax2.set_xticks(x)
ax2.set_ylim(0, yearly_mfg['count'].max() * 1.18)

fig.suptitle('图 1  样本结构图', fontsize=13, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig(fig, 'fig01_sample_structure')

# ============================================================
# Figure 2: Manufacturing annual trends (4-panel)
# ============================================================
print('Generating Figure 2: Manufacturing annual trends...')
mfg = bench[bench['manufacturing'] == 1]
mfg_annual = mfg.groupby('year').agg(
    rd_expense_mean=('rd_expense', lambda x: x.mean() / 1e8),
    rd_intensity_mean=('rd_intensity', 'mean'),
    inv_apply_mean=('invention_apply', 'mean'),
    inv_grant_mean=('invention_grant', 'mean'),
).reset_index()

fig, axes = plt.subplots(2, 2, figsize=(12, 9))
panels = [
    (axes[0,0], 'rd_expense_mean', '研发支出（亿元）', C_MFG),
    (axes[0,1], 'rd_intensity_mean', '研发强度（%）', C_MFG),
    (axes[1,0], 'inv_apply_mean', '发明专利申请（件）', C_MFG),
    (axes[1,1], 'inv_grant_mean', '发明专利授权（件）', C_MFG),
]

for ax, col, ylabel, color in panels:
    ax.plot(mfg_annual['year'], mfg_annual[col], color=color, linewidth=2.5,
            marker='s', markersize=8, markerfacecolor='white', markeredgewidth=2)
    ax.axvline(x=2021, color=C_POLICY, linestyle='--', linewidth=1.2, alpha=0.8)
    ax.text(2021.05, ax.get_ylim()[1] * 0.92, '2021年\n政策时点', color=C_POLICY,
            fontsize=8, va='top')
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_xlabel('年份', fontsize=9)
    ax.set_xticks([2017, 2018, 2019, 2020, 2021, 2022])
    ax.grid(True, alpha=0.25)
    # Annotate values
    for _, row in mfg_annual.iterrows():
        yr = int(row['year'])
        val = row[col]
        ax.annotate(f'{val:.1f}', (yr, val), textcoords="offset points",
                    xytext=(0, 10), ha='center', fontsize=7, color='#333333')

fig.suptitle('图 2  制造业研发投入与专利产出年度趋势图', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig(fig, 'fig02_mfg_trend')

# ============================================================
# Figure 3: Manufacturing vs Non-manufacturing trend comparison
# ============================================================
print('Generating Figure 3: Mfg vs Non-mfg trends...')
trend_vars = [
    ('ln_rd_expense_10k', 'ln(研发支出)', 'A. 研发支出（万元对数）'),
    ('ln_invention_apply', 'ln(发明申请)', 'B. 发明专利申请（对数）'),
    ('eff_apply_rd_10k', '发明申请/研发支出效率', 'C. 创新效率（对数差分）'),
]

fig, axes = plt.subplots(1, 3, figsize=(16, 5))

for ax, (var, ylabel, title) in zip(axes, trend_vars):
    for mfg_val, label, color, marker, ls in [
        (1, '制造业', C_MFG, 's', '-'),
        (0, '非制造业', C_NONMFG, 'o', '--'),
    ]:
        subset = bench[bench['manufacturing'] == mfg_val]
        yearly = subset.groupby('year')[var].mean()
        ax.plot(yearly.index, yearly.values, color=color, linestyle=ls,
                linewidth=2.2, marker=marker, markersize=7,
                markerfacecolor='white' if mfg_val == 1 else 'white',
                markeredgewidth=2, label=label)
    ax.axvline(x=2021, color=C_POLICY, linestyle='--', linewidth=1.2, alpha=0.8)
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_xlabel('年份', fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(True, alpha=0.25)
    ax.set_xticks([2017, 2018, 2019, 2020, 2021, 2022])

fig.suptitle('图 3  制造业与非制造业主要变量趋势对比图', fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
save_fig(fig, 'fig03_mfg_vs_nonmfg')

# ============================================================
# Figure 4: Variable distribution
# ============================================================
print('Generating Figure 4: Variable distributions...')
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

dist_vars = [
    ('ln_invention_apply', 'ln(发明专利申请)', 'A. 发明专利申请'),
    ('ln_rd_expense_10k', 'ln(研发支出, 万元)', 'B. 研发支出'),
    ('eff_apply_rd_10k', '发明申请/研发支出效率', 'C. 创新效率'),
]

for ax, (var, xlabel, title) in zip(axes, dist_vars):
    s = bench[var].dropna()
    # Clip for display
    lo, hi = s.quantile(0.01), s.quantile(0.99)
    display = s[(s >= lo) & (s <= hi)]
    ax.hist(display, bins=50, color=C_MFG, alpha=0.7, edgecolor='white', linewidth=0.3)
    ax.axvline(display.median(), color=C_POLICY, linestyle='--', linewidth=1.2,
               label=f'中位数: {display.median():.2f}')
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel('频数', fontsize=9)
    ax.legend(fontsize=8, frameon=False)

fig.suptitle('图 4  主要变量分布图', fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
save_fig(fig, 'fig04_distributions')

# ============================================================
# Figure 5: Pre-post group means
# ============================================================
print('Generating Figure 5: Pre-post group means...')
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

prepost_vars = [
    ('ln_rd_expense_10k', 'ln(研发支出)', 'A. 研发支出'),
    ('ln_invention_apply', 'ln(发明申请)', 'B. 发明专利申请'),
    ('eff_apply_rd_10k', '发明申请/研发支出效率', 'C. 创新效率'),
]

for ax, (var, ylabel, title) in zip(axes, prepost_vars):
    groups = []
    positions = []
    labels = []
    colors_list = []
    patterns = []

    for i, (mfg_val, mfg_label) in enumerate([(1, '制造业'), (0, '非制造业')]):
        for j, (post_val, post_label) in enumerate([(0, '政策前'), (1, '政策后')]):
            subset = bench[(bench['manufacturing'] == mfg_val) & (bench['post2021'] == post_val)]
            val = subset[var].mean()
            groups.append(val)
            pos = i * 3 + j
            positions.append(pos)
            labels.append(f'{mfg_label}\n{post_label}')
            if mfg_val == 1:
                colors_list.append(C_MFG)
                patterns.append('' if post_val == 0 else C_HATCH1)
            else:
                colors_list.append(C_NONMFG)
                patterns.append('' if post_val == 0 else C_HATCH2)

    bars = ax.bar(positions, groups, color=colors_list, edgecolor='black', linewidth=0.8)
    # Add hatch for post-policy bars
    for bar, pat in zip(bars, patterns):
        if pat:
            bar.set_hatch(pat)

    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, alpha=0.25, axis='y')

# Add a legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor=C_MFG, label='制造业', edgecolor='black'),
    Patch(facecolor=C_NONMFG, label='非制造业', edgecolor='black'),
    Patch(facecolor='white', hatch=C_HATCH1, label='政策后', edgecolor='black'),
]
fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=9, frameon=False,
           bbox_to_anchor=(0.5, -0.03))

fig.suptitle('图 5  政策前后分组均值变化图', fontsize=14, fontweight='bold', y=1.03)
plt.tight_layout()
save_fig(fig, 'fig05_prepost_means')

# ============================================================
# Figure 6: Main DID forest plot
# ============================================================
print('Generating Figure 6: Main DID forest plot...')
fig, ax = plt.subplots(figsize=(10, 7))

forest_data = [
    # (label, coef, se, p, category)
    ('发明专利申请', -0.0247, 0.0246, 0.3146, 'A. 创新数量'),
    ('发明专利授权', -0.0113, 0.0230, 0.6224, 'A. 创新数量'),
    ('专利总申请', -0.0017, 0.0339, 0.9591, 'A. 创新数量'),
    ('专利总授权', 0.0348, 0.0357, 0.3298, 'A. 创新数量'),
    ('研发支出', -0.2884, 0.0568, 0.0000, 'B. 研发投入'),
    ('研发强度', -0.0029, 0.0013, 0.0245, 'B. 研发投入'),
    ('研发人员', -0.1971, 0.0443, 0.0000, 'B. 研发投入'),
    ('研发人员占比', 0.0002, 0.0029, 0.9509, 'B. 研发投入'),
    ('发明申请/研发支出效率', 0.2637, 0.0616, 0.0000, 'C. 创新效率'),
    ('发明授权/研发支出效率', 0.2771, 0.0611, 0.0000, 'C. 创新效率'),
    ('发明申请/研发人员效率', 0.1724, 0.0499, 0.0005, 'C. 创新效率'),
    ('发明授权/研发人员效率', 0.1858, 0.0491, 0.0002, 'C. 创新效率'),
]

n = len(forest_data)
y_positions = list(range(n))

# Category backgrounds
categories_order = ['A. 创新数量', 'B. 研发投入', 'C. 创新效率']
cat_ranges = {}
for cat in categories_order:
    indices = [i for i, d in enumerate(forest_data) if d[4] == cat]
    if indices:
        cat_ranges[cat] = (min(indices), max(indices))

for cat, (lo, hi) in cat_ranges.items():
    ax.axhspan(lo - 0.5, hi + 0.5, alpha=0.06, color='black', zorder=0)
    ax.text(0.98, hi + 0.3, cat, transform=ax.get_yaxis_transform(), ha='right',
            fontsize=9, fontweight='bold', va='bottom')

for i, (label, coef, se, p, cat) in enumerate(forest_data):
    ci_low = coef - 1.96 * se
    ci_high = coef + 1.96 * se

    if p < 0.01:
        color = C_SIG_POS if coef > 0 else C_SIG_NEG
        marker = 'D'
        ms = 7
    elif p < 0.05:
        color = C_SIG_POS if coef > 0 else C_SIG_NEG
        marker = 's'
        ms = 6
    elif p < 0.10:
        color = '#777777'
        marker = '^' if coef > 0 else 'v'
        ms = 6
    else:
        color = C_NS
        marker = 'o'
        ms = 5

    ax.errorbar(coef, n - 1 - i, xerr=[[coef - ci_low], [ci_high - coef]],
                fmt=marker, color=color, capsize=3, markersize=ms,
                markeredgecolor='black', markeredgewidth=0.5, linewidth=1.5)
    sig_str = fmt_sig(p)
    text_x = max(coef + 0.015, 0.01) if coef >= 0 else min(coef - 0.015, -0.01)
    ha = 'left' if coef >= 0 else 'right'
    ax.text(coef + (0.02 if coef >= 0 else -0.02), n - 1 - i,
            f'{coef:+.3f}{sig_str}', va='center', ha=ha, fontsize=8,
            fontweight='bold' if p < 0.05 else 'normal')

ax.set_yticks([n - 1 - i for i in range(n)])
ax.set_yticklabels([d[0] for d in forest_data], fontsize=8.5)
ax.axvline(x=0, color='black', linewidth=1, linestyle='-')
ax.set_xlabel('DID 系数（制造业 × 政策后）', fontsize=10)
ax.set_title('图 6  基准 DID 估计结果森林图', fontsize=13, fontweight='bold')
ax.grid(True, alpha=0.2, axis='x')

# Add significance legend
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker='D', color='w', markerfacecolor=C_SIG_POS, markersize=8, label='p < 0.01'),
    Line2D([0], [0], marker='s', color='w', markerfacecolor=C_SIG_POS, markersize=7, label='p < 0.05'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor=C_NS, markersize=6, label='不显著'),
]
ax.legend(handles=legend_elements, fontsize=8, loc='lower right', frameon=True, fancybox=True)

plt.tight_layout()
save_fig(fig, 'fig06_did_forest')

# ============================================================
# Figure 7: Efficiency decomposition (waterfall style)
# ============================================================
print('Generating Figure 7: Efficiency decomposition...')
fig, ax = plt.subplots(figsize=(9, 5.5))

# Waterfall data
items = [
    ('DID(发明专利申请)\nln(发明申请)', -0.0247, C_NONMFG),
    ('−DID(研发支出)\nln(研发支出)', 0.2884, C_SIG_POS),   # minus a negative = positive
    ('= DID(创新效率)\n发明申请/研发支出', 0.2637, C_EFF),
]

# Build waterfall
cumulative = 0
bar_colors = []
bar_values = []
bar_labels = []
for i, (label, val, color) in enumerate(items):
    bar_values.append(val)
    bar_labels.append(label)
    bar_colors.append(color)

# Draw the first bar
ax.bar(0, bar_values[0], color=bar_colors[0], edgecolor='black', linewidth=0.8, width=0.5)
# Draw the second bar (starts from first bar's end)
ax.bar(1, bar_values[1], bottom=bar_values[0], color=bar_colors[1],
       edgecolor='black', linewidth=0.8, width=0.5, hatch=C_HATCH1)
# Draw the total bar
total = bar_values[0] + bar_values[1]
ax.bar(2, total, color=bar_colors[2], edgecolor='black', linewidth=0.8, width=0.5)

# Add connector lines
ax.plot([0.25, 0.75], [bar_values[0], bar_values[0]], 'k-', linewidth=1)
# Dashed line from top of bar 1 to top of stacked area
stack_top = bar_values[0] + bar_values[1]
ax.plot([0.25, 0.75], [bar_values[0], stack_top], 'k--', linewidth=0.8, alpha=0.5)

# Annotations
for i, (val, label) in enumerate(zip(bar_values, bar_labels)):
    if i == 1:
        y_pos = bar_values[0] + val / 2
    else:
        y_pos = val / 2 if val < 0 else val * 0.4
    color = 'white' if abs(val) > 0.15 else 'black'
    ax.text(i, y_pos if i != 1 else bar_values[0] + val/2,
            f'{val:+.4f}', ha='center', va='center', fontsize=12, fontweight='bold', color=color)

# Total annotation
ax.text(2, total / 2, f'{total:+.4f}', ha='center', va='center', fontsize=13,
        fontweight='bold', color='white')

ax.set_xticks([0, 1, 2])
ax.set_xticklabels(bar_labels, fontsize=9)
ax.axhline(y=0, color='black', linewidth=1)
ax.set_ylabel('DID 系数', fontsize=10)
ax.set_title('图 7  创新效率来源拆解图', fontsize=13, fontweight='bold')
ax.grid(True, alpha=0.2, axis='y')

# Add explanatory text
ax.text(0.5, -0.18, '效率改善 ≈ 研发投入相对增长较慢 − 专利数量相对变化不显著',
        transform=ax.transAxes, ha='center', fontsize=9, fontstyle='italic',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgray', alpha=0.5))

plt.tight_layout()
save_fig(fig, 'fig07_efficiency_decomp')

# ============================================================
# Figure 8: Heterogeneity heatmap
# ============================================================
print('Generating Figure 8: Heterogeneity heatmap...')
fig, ax = plt.subplots(figsize=(10, 4.5))

het_data = [
    # (row_label, col_label, coef, se, p)
    ('高研发基础\n交互项', '发明申请/\n研发支出', 0.2253, 0.0509, 0.0000),
    ('高研发基础\n交互项', '发明授权/\n研发支出', 0.2718, 0.0484, 0.0000),
    ('高研发基础\n交互项', '发明申请/\n研发人员', 0.1368, 0.0534, 0.0104),
    ('高研发基础\n交互项', '发明授权/\n研发人员', 0.1833, 0.0512, 0.0003),
    ('制造业内部\n高研发暴露', '发明申请/\n研发支出', 0.1977, 0.0503, 0.0001),
    ('制造业内部\n高研发暴露', '发明授权/\n研发支出', 0.2445, 0.0476, 0.0000),
    ('制造业内部\n高研发暴露', '发明申请/\n研发人员', 0.1236, 0.0537, 0.0215),
    ('制造业内部\n高研发暴露', '发明授权/\n研发人员', 0.1704, 0.0514, 0.0009),
]

rows = sorted(set(d[0] for d in het_data))
cols = sorted(set(d[1] for d in het_data))
n_rows, n_cols = len(rows), len(cols)

# Build matrix
matrix = np.zeros((n_rows, n_cols))
annot = [['' for _ in range(n_cols)] for _ in range(n_rows)]

for row_label, col_label, coef, se, p in het_data:
    ri = rows.index(row_label)
    ci = cols.index(col_label)
    matrix[ri, ci] = coef
    sig = fmt_sig(p)
    annot[ri][ci] = f'{coef:.3f}{sig}'

im = ax.imshow(matrix, cmap='RdBu_r', aspect='auto', vmin=-0.05, vmax=0.35)

# Annotate cells
for i in range(n_rows):
    for j in range(n_cols):
        val = matrix[i, j]
        text_color = 'white' if abs(val) > 0.2 else 'black'
        ax.text(j, i, annot[i][j], ha='center', va='center', fontsize=11,
                fontweight='bold', color=text_color)

ax.set_xticks(range(n_cols))
ax.set_xticklabels(cols, fontsize=9)
ax.set_yticks(range(n_rows))
ax.set_yticklabels(rows, fontsize=9)

# Colorbar
cbar = plt.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
cbar.set_label('系数', fontsize=9)

ax.set_title('图 8  异质性分析结果图', fontsize=13, fontweight='bold')
plt.tight_layout()
save_fig(fig, 'fig08_heterogeneity')

# ============================================================
# Figure 9: Baseline vs Stronger FE comparison
# ============================================================
print('Generating Figure 9: Baseline vs Stronger FE...')
fig, ax = plt.subplots(figsize=(9, 5))

fe_data = [
    ('发明申请/\n研发支出', 0.2637, 0.0616, 0.2552, 0.0635),
    ('发明授权/\n研发支出', 0.2771, 0.0611, 0.2903, 0.0632),
    ('发明申请/\n研发人员', 0.1724, 0.0499, 0.1614, 0.0512),
    ('发明授权/\n研发人员', 0.1858, 0.0491, 0.1965, 0.0506),
]

x = np.arange(len(fe_data))
width = 0.35

for i, (label, base_coef, base_se, strong_coef, strong_se) in enumerate(fe_data):
    # Baseline
    ax.bar(i - width/2, base_coef, width, yerr=base_se * 1.96,
           color=C_NONMFG, edgecolor='black', linewidth=0.8, capsize=4,
           label='基准模型 (Firm+Year FE)' if i == 0 else '')
    # Stronger FE
    ax.bar(i + width/2, strong_coef, width, yerr=strong_se * 1.96,
           color=C_MFG, edgecolor='black', linewidth=0.8, capsize=4,
           hatch=C_HATCH1, label='强固定效应 (Firm+Year+Prov×Year)' if i == 0 else '')

ax.set_xticks(x)
ax.set_xticklabels([d[0] for d in fe_data], fontsize=9)
ax.axhline(y=0, color='black', linewidth=0.8)
ax.set_ylabel('DID 系数', fontsize=10)
ax.set_title('图 9  基准模型与强固定效应模型结果对比图', fontsize=13, fontweight='bold')
ax.legend(fontsize=8, frameon=False, loc='upper right')
ax.grid(True, alpha=0.2, axis='y')
plt.tight_layout()
save_fig(fig, 'fig09_stronger_fe')

# ============================================================
# Figure 10: Event study (3 panels)
# ============================================================
print('Generating Figure 10: Event study...')
event_data_dict = {
    'A. 发明专利申请\nln(发明申请)': {
        2017: (0.0031, 0.0333), 2018: (-0.0319, 0.0311),
        2019: (-0.0142, 0.0302), 2020: (0.0, 0.0),
        2021: (-0.0334, 0.0278), 2022: (-0.0352, 0.0314),
    },
    'B. 研发支出\nln(研发支出)': {
        2017: (0.6871, 0.1034), 2018: (0.3962, 0.0774),
        2019: (0.2963, 0.0575), 2020: (0.0, 0.0),
        2021: (0.0101, 0.0550), 2022: (-0.0021, 0.0661),
    },
    'C. 创新效率\n发明申请/研发支出': {
        2017: (-0.6840, 0.1074), 2018: (-0.4281, 0.0829),
        2019: (-0.3104, 0.0642), 2020: (0.0, 0.0),
        2021: (-0.0435, 0.0610), 2022: (-0.0330, 0.0724),
    },
}

fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))

for ax, (title, data) in zip(axes, event_data_dict.items()):
    years = sorted(data.keys())
    coefs = [data[y][0] for y in years]
    ses = [data[y][1] for y in years]

    # Plot: exclude baseline year
    plot_years = [y for y in years if y != 2020]
    plot_coefs = [data[y][0] for y in plot_years]
    plot_ses = [data[y][1] for y in plot_years]
    ci_lows = [c - 1.96 * s for c, s in zip(plot_coefs, plot_ses)]
    ci_highs = [c + 1.96 * s for c, s in zip(plot_coefs, plot_ses)]

    ax.errorbar(plot_years, plot_coefs,
                yerr=[np.array(plot_coefs) - np.array(ci_lows), np.array(ci_highs) - np.array(plot_coefs)],
                fmt='s-', color=C_MFG, capsize=5, markersize=8,
                markerfacecolor='white', markeredgewidth=2, linewidth=2, label='事件系数')

    # Baseline year
    ax.plot(2020, 0, 'D', color=C_POLICY, markersize=10, markerfacecolor=C_POLICY,
            label='2020（基准年）')

    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.axvline(x=2020.5, color=C_POLICY, linestyle='--', linewidth=1.5, alpha=0.8)
    ax.text(2020.55, ax.get_ylim()[1] * 0.92, '2021\n政策', color=C_POLICY, fontsize=8, va='top')

    # Shade pre-policy area
    ax.axvspan(2016.5, 2020.5, alpha=0.04, color='black')

    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.set_xlabel('年份', fontsize=9)
    ax.set_xticks([2017, 2018, 2019, 2020, 2021, 2022])
    ax.grid(True, alpha=0.2)
    ax.legend(fontsize=7, frameon=False, loc='upper left')

fig.suptitle('图 10  事件研究结果图（基准年 = 2020）', fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
save_fig(fig, 'fig10_event_study')

# ============================================================
# Figure 11: Placebo test
# ============================================================
print('Generating Figure 11: Placebo test...')
fig, ax = plt.subplots(figsize=(8, 4.5))

placebo_eff_data = [
    ('真实政策时点\n2021年', 0.2637, 0.0616, C_MFG),
    ('假想政策时点\n2019年', 0.2902, 0.0719, C_NONMFG),
    ('假想政策时点\n2020年', 0.3252, 0.0701, C_SIG_NEG),
]

x_pos = [0, 1, 2]
for i, (label, coef, se, color) in enumerate(placebo_eff_data):
    ax.bar(i, coef, color=color, yerr=se * 1.96, capsize=6, width=0.5,
           edgecolor='black', linewidth=0.8, alpha=0.85)
    ax.text(i, coef + 0.02, f'{coef:+.4f}{fmt_sig(coef/se if se > 0 else 999)}',
            ha='center', fontsize=10, fontweight='bold')

ax.set_xticks(x_pos)
ax.set_xticklabels([d[0] for d in placebo_eff_data], fontsize=10)
ax.axhline(y=0, color='black', linewidth=0.8)
ax.set_ylabel('DID 系数 (eff_apply_rd_10k)', fontsize=10)
ax.set_title('图 11  安慰剂检验结果图', fontsize=13, fontweight='bold')
ax.grid(True, alpha=0.2, axis='y')

# Add annotation
ax.annotate('假想时点也显著为正\n→ 效率差距在政策前\n   已存在收敛趋势',
            xy=(1.8, 0.27), fontsize=9, color='#555555',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

plt.tight_layout()
save_fig(fig, 'fig11_placebo')

# ============================================================
# Figure 12: Policy timeline
# ============================================================
print('Generating Figure 12: Policy timeline...')
fig, ax = plt.subplots(figsize=(11, 3.5))

periods = [
    (2016.5, 2018, '#E8E8E8', '50%', '2018年前'),
    (2018, 2021, '#CCCCCC', '75%', '2018-2020\n符合条件企业75%'),
    (2021, 2023, '#999999', '制造业\n100%', '2021-2022\n制造业100%'),
    (2023, 2025.5, '#777777', '全体\n100%', '2023年起\n全行业100%'),
]

for start, end, color, label, desc in periods:
    ax.axvspan(start, end, alpha=0.25, color=color)
    mid = (start + end) / 2
    ax.text(mid, 0.65, desc, ha='center', va='center', fontsize=9, fontweight='bold')

# Highlight DID identification window
ax.axvspan(2021, 2023, alpha=0.12, color='black')
ax.annotate('DID识别窗口\n（制造业 vs 非制造业\n差异化激励）',
            xy=(2022, 0.35), fontsize=9, ha='center', fontweight='bold',
            color=C_POLICY,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor=C_POLICY))

# Policy annotations
policy_annotations = [
    (2018, '财税〔2018〕\n99号', '75%'),
    (2021, '财政部公告\n2021年第13号', '制造业\n100%'),
    (2022, '三部门公告\n2022年第16号', '科技型\n中小企业\n100%'),
    (2023, '财政部公告\n2023年第7号', '全行业\n100%'),
    (2023.7, '四部门公告\n2023年第44号', '集成电路/\n工业母机\n120%'),
]

for year, doc, rate in policy_annotations:
    ax.axvline(x=year, color=C_POLICY, linestyle='-', linewidth=1.5, alpha=0.7)
    ax.text(year, 0.15, f'{doc}\n{rate}', ha='center', fontsize=7,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.85,
                      edgecolor='#999999'))

ax.set_xlim(2016, 2026)
ax.set_ylim(0, 1)
ax.set_yticks([])
ax.set_xlabel('年份', fontsize=10)
ax.set_title('图 12  研发费用加计扣除政策时间轴', fontsize=13, fontweight='bold')

# Remove spines
for spine in ['top', 'right', 'left']:
    ax.spines[spine].set_visible(False)

plt.tight_layout()
save_fig(fig, 'fig12_policy_timeline')

# ============================================================
print('\nAll 12 figures generated in:', OUTPUT_DIR)
print('Files:')
for f in sorted(os.listdir(OUTPUT_DIR)):
    print(f'  {f}')
