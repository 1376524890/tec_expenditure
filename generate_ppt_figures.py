#!/usr/bin/env python3
"""
Generate all 12 figures with academic-style color palettes for PPT use.
Low saturation, professional colors suitable for presentations.
Output: outputs/figures_ppt/
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import os
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = 'outputs/figures_ppt'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# Academic color palette — low saturation, PPT-friendly
# ============================================================
# Muted, professional palette inspired by scientific journals
C_BLUE      = '#4472C4'   # soft blue
C_ORANGE    = '#ED7D31'   # muted orange
C_RED       = '#C0504D'   # brick red
C_GREEN     = '#548235'   # forest green
C_PURPLE    = '#8064A2'   # muted purple
C_TEAL      = '#5B9BD5'   # steel teal
C_GOLD      = '#BF8F00'   # dark gold
C_GRAY      = '#A5A5A5'   # neutral gray
C_DARK      = '#404040'   # dark gray for text
C_WHITE     = '#FFFFFF'

# Semantic assignments
C_MFG       = C_BLUE       # manufacturing
C_NONMFG    = C_ORANGE     # non-manufacturing
C_POLICY    = C_RED        # policy line
C_EFF       = C_GREEN      # efficiency
C_SIG_POS   = C_GREEN      # significant positive
C_SIG_NEG   = C_RED        # significant negative
C_NS        = C_GRAY       # non-significant
C_STRONG_FE = C_PURPLE     # stronger FE
C_HATCH1    = '///'
C_HATCH2    = '\\\\\\'

# Figure-wide defaults
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

bench['rd_intensity_01'] = bench['rd_intensity'] / 100
bench['ln_rd_expense_10k'] = np.log1p(bench['rd_expense'] / 10000)
bench['post2021'] = (bench['year'] >= 2021).astype(int)
bench['eff_apply_rd_10k'] = bench['ln_invention_apply'] - bench['ln_rd_expense_10k']
bench['eff_grant_rd_10k'] = bench['ln_invention_grant'] - bench['ln_rd_expense_10k']
bench['eff_apply_staff'] = bench['ln_invention_apply'] - bench['ln_rd_staff']
bench['eff_grant_staff'] = bench['ln_invention_grant'] - bench['ln_rd_staff']


def add_policy_vline(ax, x=2021):
    ax.axvline(x=x, color=C_POLICY, linestyle='--', linewidth=1.5, alpha=0.8)


def add_zero_hline(ax):
    ax.axhline(y=0, color='black', linewidth=0.8)


# ============================================================
# Figure 1: Sample Structure
# ============================================================
print('Figure 1: Sample Structure')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

# Pie
sizes = [16740, 10032]
labels = ['制造业\n(16,740条, 62.5%)', '非制造业\n(10,032条, 37.5%)']
colors_pie = [C_MFG, C_NONMFG]
wedges, texts, autotexts = ax1.pie(sizes, labels=None, colors=colors_pie, startangle=90,
                                     autopct='%1.1f%%', pctdistance=0.6,
                                     wedgeprops={'edgecolor': 'white', 'linewidth': 1.5},
                                     textprops={'fontsize': 9})
for autotext in autotexts:
    autotext.set_fontweight('bold')
ax1.legend(wedges, labels, loc='lower center', fontsize=9, frameon=True, fancybox=True)
ax1.set_title('样本结构', fontsize=13, fontweight='bold', color=C_DARK)

# Bar by year
yearly = bench.groupby('year')['manufacturing'].agg(['sum', 'count']).reset_index()
yearly['nonmfg'] = yearly['count'] - yearly['sum']
yearly['mfg_pct'] = yearly['sum'] / yearly['count'] * 100

x = yearly['year'].values
ax2.bar(x, yearly['nonmfg'], color=C_NONMFG, label='非制造业', edgecolor='white', linewidth=0.5)
ax2.bar(x, yearly['sum'], bottom=yearly['nonmfg'], color=C_MFG,
        label='制造业', edgecolor='white', linewidth=0.5)
for i, yr in enumerate(x):
    ax2.text(yr, yearly['count'].values[i] + 100,
             f'{yearly["mfg_pct"].values[i]:.1f}%', ha='center', fontsize=8,
             fontweight='bold', color=C_DARK)
ax2.set_title('分年度样本构成', fontsize=13, fontweight='bold', color=C_DARK)
ax2.set_xlabel('年份')
ax2.set_ylabel('观测数')
ax2.legend(fontsize=9, frameon=True, fancybox=True)
ax2.set_xticks(x)
ax2.set_ylim(0, yearly['count'].max() * 1.18)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

fig.suptitle('图 1  样本结构图', fontsize=14, fontweight='bold', color=C_DARK, y=1.01)
plt.tight_layout()
save_fig(fig, 'fig01_sample_structure')


# ============================================================
# Figure 2: Manufacturing Annual Trends (4-panel)
# ============================================================
print('Figure 2: Manufacturing Trends')
mfg = bench[bench['manufacturing'] == 1]
mfg_a = mfg.groupby('year').agg(
    rd=('rd_expense', lambda x: x.mean() / 1e8),
    rd_int=('rd_intensity', 'mean'),
    inv_app=('invention_apply', 'mean'),
    inv_grt=('invention_grant', 'mean'),
).reset_index()

fig, axes = plt.subplots(2, 2, figsize=(12, 9))
panels = [
    (axes[0,0], 'rd', '研发支出（亿元）', C_BLUE),
    (axes[0,1], 'rd_int', '研发强度（%）', C_GREEN),
    (axes[1,0], 'inv_app', '发明专利申请（件）', C_ORANGE),
    (axes[1,1], 'inv_grt', '发明专利授权（件）', C_TEAL),
]
for ax, col, ylabel, color in panels:
    ax.plot(mfg_a['year'], mfg_a[col], color=color, linewidth=2.8,
            marker='D', markersize=9, markerfacecolor='white',
            markeredgewidth=2.5, markeredgecolor=color)
    add_policy_vline(ax)
    ax.text(2021.08, ax.get_ylim()[1]*0.92, '2021年\n政策时点', color=C_POLICY,
            fontsize=8, va='top', fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=10, color=C_DARK)
    ax.set_xlabel('年份', fontsize=10)
    ax.set_xticks([2017, 2018, 2019, 2020, 2021, 2022])
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for _, row in mfg_a.iterrows():
        yr = int(row['year'])
        ax.annotate(f'{row[col]:.1f}', (yr, row[col]), textcoords="offset points",
                    xytext=(0, 12), ha='center', fontsize=7.5, color=C_DARK,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))

fig.suptitle('图 2  制造业研发投入与专利产出年度趋势图', fontsize=14, fontweight='bold', color=C_DARK, y=1.01)
plt.tight_layout()
save_fig(fig, 'fig02_mfg_trend')


# ============================================================
# Figure 3: Mfg vs Non-mfg Trend Comparison (3-panel)
# ============================================================
print('Figure 3: Mfg vs Non-mfg Trends')
fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
trend_cfg = [
    ('ln_rd_expense_10k', 'ln(研发支出)', 'A. 研发支出（万元对数）'),
    ('ln_invention_apply', 'ln(发明申请)', 'B. 发明专利申请（对数）'),
    ('eff_apply_rd_10k', '发明申请/研发支出效率', 'C. 创新效率（对数差分）'),
]
for ax, (var, ylabel, title) in zip(axes, trend_cfg):
    for mfg_val, label, color, marker, ls in [
        (1, '制造业', C_BLUE, 'D', '-'),
        (0, '非制造业', C_ORANGE, 'o', '--'),
    ]:
        subset = bench[bench['manufacturing'] == mfg_val]
        yearly = subset.groupby('year')[var].mean()
        ax.plot(yearly.index, yearly.values, color=color, linestyle=ls,
                linewidth=2.5, marker=marker, markersize=8,
                markerfacecolor='white', markeredgewidth=2.5, label=label)
    add_policy_vline(ax)
    ax.set_title(title, fontsize=12, fontweight='bold', color=C_DARK)
    ax.set_xlabel('年份')
    ax.set_ylabel(ylabel)
    ax.legend(fontsize=9, frameon=True, fancybox=True, loc='upper left')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xticks([2017, 2018, 2019, 2020, 2021, 2022])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

fig.suptitle('图 3  制造业与非制造业主要变量趋势对比图', fontsize=14, fontweight='bold', color=C_DARK, y=1.02)
plt.tight_layout()
save_fig(fig, 'fig03_mfg_vs_nonmfg')


# ============================================================
# Figure 4: Variable Distributions (3-panel histogram)
# ============================================================
print('Figure 4: Variable Distributions')
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
dist_cfg = [
    ('ln_invention_apply', 'ln(发明专利申请)', 'A. 发明专利申请', C_BLUE),
    ('ln_rd_expense_10k', 'ln(研发支出, 万元)', 'B. 研发支出', C_ORANGE),
    ('eff_apply_rd_10k', '发明申请/研发支出效率', 'C. 创新效率', C_GREEN),
]
for ax, (var, xlabel, title, color) in zip(axes, dist_cfg):
    s = bench[var].dropna()
    lo, hi = s.quantile(0.01), s.quantile(0.99)
    display = s[(s >= lo) & (s <= hi)]
    ax.hist(display, bins=60, color=color, alpha=0.6, edgecolor='white', linewidth=0.5)
    ax.axvline(display.median(), color=C_RED, linestyle='--', linewidth=2,
               label=f'中位数: {display.median():.2f}')
    ax.set_title(title, fontsize=12, fontweight='bold', color=C_DARK)
    ax.set_xlabel(xlabel)
    ax.set_ylabel('频数')
    ax.legend(fontsize=9, frameon=True, fancybox=True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

fig.suptitle('图 4  主要变量分布图', fontsize=14, fontweight='bold', color=C_DARK, y=1.02)
plt.tight_layout()
save_fig(fig, 'fig04_distributions')


# ============================================================
# Figure 5: Pre-Post Group Means (3-panel grouped bar)
# ============================================================
print('Figure 5: Pre-Post Means')
fig, axes = plt.subplots(1, 3, figsize=(14, 5))
pp_cfg = [
    ('ln_rd_expense_10k', 'ln(研发支出)', 'A. 研发支出'),
    ('ln_invention_apply', 'ln(发明申请)', 'B. 发明专利申请'),
    ('eff_apply_rd_10k', '发明申请/研发支出效率', 'C. 创新效率'),
]
width = 0.35
for ax, (var, ylabel, title) in zip(axes, pp_cfg):
    groups = {}
    for mfg_val, mfg_label, color in [(1, '制造业', C_BLUE), (0, '非制造业', C_ORANGE)]:
        for post_val, post_label, hatch in [(0, '政策前', ''), (1, '政策后', '//')]:
            subset = bench[(bench['manufacturing']==mfg_val) & (bench['post2021']==post_val)]
            key = f'{mfg_label}-{post_label}'
            groups[key] = (subset[var].mean(), color, hatch)

    x = np.arange(2)
    bars_pre = ax.bar(x - width/2, [groups['制造业-政策前'][0], groups['非制造业-政策前'][0]],
                      width, color=[C_BLUE, C_ORANGE], edgecolor='white', linewidth=0.8, alpha=0.85)
    bars_post = ax.bar(x + width/2, [groups['制造业-政策后'][0], groups['非制造业-政策后'][0]],
                       width, color=[C_BLUE, C_ORANGE], edgecolor='white', linewidth=0.8,
                       alpha=0.85, hatch='//')
    ax.set_xticks(x)
    ax.set_xticklabels(['制造业', '非制造业'], fontsize=10)
    ax.set_title(title, fontsize=12, fontweight='bold', color=C_DARK)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

legend_el = [
    Patch(facecolor=C_BLUE, alpha=0.85, label='制造业 政策前'),
    Patch(facecolor=C_ORANGE, alpha=0.85, label='非制造业 政策前'),
    Patch(facecolor=C_BLUE, alpha=0.85, hatch='//', label='制造业 政策后'),
    Patch(facecolor=C_ORANGE, alpha=0.85, hatch='//', label='非制造业 政策后'),
]
fig.legend(handles=legend_el, loc='lower center', ncol=4, fontsize=9,
           frameon=True, fancybox=True, bbox_to_anchor=(0.5, -0.04))
fig.suptitle('图 5  政策前后分组均值变化图', fontsize=14, fontweight='bold', color=C_DARK, y=1.04)
plt.tight_layout()
save_fig(fig, 'fig05_prepost_means')


# ============================================================
# Figure 6: DID Forest Plot
# ============================================================
print('Figure 6: DID Forest Plot')
fig, ax = plt.subplots(figsize=(10.5, 7.5))

forest_data = [
    ('发明专利申请', -0.0247, 0.0246, 0.3146, 'A. 创新数量'),
    ('发明专利授权', -0.0113, 0.0230, 0.6224, 'A. 创新数量'),
    ('专利总申请', -0.0017, 0.0339, 0.9591, 'A. 创新数量'),
    ('专利总授权', 0.0348, 0.0357, 0.3298, 'A. 创新数量'),
    ('研发支出（万元对数）', -0.2884, 0.0568, 0.0000, 'B. 研发投入'),
    ('研发强度 (0-1)', -0.0029, 0.0013, 0.0245, 'B. 研发投入'),
    ('研发人员（对数）', -0.1971, 0.0443, 0.0000, 'B. 研发投入'),
    ('研发人员占比 (0-1)', 0.0002, 0.0029, 0.9509, 'B. 研发投入'),
    ('发明申请 / 研发支出效率', 0.2637, 0.0616, 0.0000, 'C. 创新效率'),
    ('发明授权 / 研发支出效率', 0.2771, 0.0611, 0.0000, 'C. 创新效率'),
    ('发明申请 / 研发人员效率', 0.1724, 0.0499, 0.0005, 'C. 创新效率'),
    ('发明授权 / 研发人员效率', 0.1858, 0.0491, 0.0002, 'C. 创新效率'),
]

n = len(forest_data)
cat_colors = {'A. 创新数量': '#E8E8E8', 'B. 研发投入': '#F0E8D8', 'C. 创新效率': '#E0F0E0'}
for cat, color in cat_colors.items():
    indices = [i for i, d in enumerate(forest_data) if d[4] == cat]
    if indices:
        lo, hi = min(indices), max(indices)
        ax.axhspan(n-1-hi-0.5, n-1-lo+0.5, alpha=0.25, facecolor=color, zorder=0, edgecolor='#CCCCCC', linewidth=0.5)
        ax.text(0.98, n-1-(lo+hi)/2, f'{cat}', transform=ax.get_yaxis_transform(),
                ha='right', fontsize=9, fontweight='bold', va='center', color=C_DARK)

for i, (label, coef, se, p, cat) in enumerate(forest_data):
    ci_low = coef - 1.96*se
    ci_high = coef + 1.96*se
    if p < 0.01:
        color = C_SIG_POS if coef > 0 else C_SIG_NEG
        marker, ms = 'D', 8
    elif p < 0.05:
        color = C_SIG_POS if coef > 0 else C_SIG_NEG
        marker, ms = 's', 7
    elif p < 0.10:
        color = '#A0A0A0'
        marker, ms = '^' if coef > 0 else 'v', 6
    else:
        color = C_GRAY
        marker, ms = 'o', 6
    ax.errorbar(coef, n-1-i, xerr=[[coef-ci_low], [ci_high-coef]],
                fmt=marker, color=color, capsize=3, markersize=ms,
                markeredgecolor='white', markeredgewidth=0.5, linewidth=2)
    sig_str = fmt_sig(p)
    x_txt = coef + (0.03 if coef >= 0 else -0.03)
    ha = 'left' if coef >= 0 else 'right'
    ax.text(x_txt, n-1-i, f'{coef:+.3f}{sig_str}', va='center', ha=ha,
            fontsize=8.5, fontweight='bold' if p < 0.05 else 'normal', color=C_DARK)

ax.set_yticks(range(n))
ax.set_yticklabels([d[0] for d in forest_data], fontsize=8.5)
add_zero_hline(ax)
ax.set_xlabel('DID 系数（制造业 × 政策后）', fontsize=11, color=C_DARK)
ax.set_title('图 6  基准 DID 估计结果森林图', fontsize=14, fontweight='bold', color=C_DARK)
ax.grid(True, alpha=0.25, axis='x', linestyle='--')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

legend_el = [
    Line2D([0],[0], marker='D', color='w', markerfacecolor=C_SIG_POS, markersize=9, label='p < 0.01'),
    Line2D([0],[0], marker='s', color='w', markerfacecolor=C_SIG_POS, markersize=7, label='p < 0.05'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor=C_GRAY, markersize=6, label='不显著'),
]
ax.legend(handles=legend_el, fontsize=8, loc='lower right', frameon=True, fancybox=True)
plt.tight_layout()
save_fig(fig, 'fig06_did_forest')


# ============================================================
# Figure 7: Efficiency Decomposition (waterfall style)
# ============================================================
print('Figure 7: Efficiency Decomposition')
fig, ax = plt.subplots(figsize=(9, 5.5))
vals = [-0.0247, 0.2884, 0.2637]
labels = ['创新产出\nDID(ln发明申请)\n−0.025', '研发投入调整\n−DID(ln研发支出)\n+0.288', '创新效率\nDID(发明申请/研发支出)\n+0.264']
colors_bar = [C_GRAY, C_ORANGE, C_GREEN]

# Bottom bar
ax.bar(0, vals[0], color=colors_bar[0], edgecolor='white', linewidth=1, width=0.5, alpha=0.85)
# Middle bar (stacked on top of bottom)
ax.bar(1, vals[1], bottom=vals[0], color=colors_bar[1], edgecolor='white', linewidth=1, width=0.5, alpha=0.85, hatch='//')
# Total
ax.bar(2, vals[2], color=colors_bar[2], edgecolor='white', linewidth=1, width=0.5, alpha=0.85)

# Connector line
ax.plot([0.25, 0.75], [vals[0], vals[0]], '-', color=C_DARK, linewidth=1.2)
ax.plot([0.25, 0.75], [vals[0], vals[0]+vals[1]], '--', color=C_DARK, linewidth=1, alpha=0.6)

# Annotations
for i, (val, label) in enumerate(zip(vals, labels)):
    if i == 0:
        mid = val/2 if val < 0 else val*0.4
        txt_color = 'black'
    elif i == 1:
        mid = vals[0] + val/2
        txt_color = 'black'
    else:
        mid = val/2
        txt_color = 'black'
    ax.text(i, mid, f'{val:+.4f}', ha='center', va='center', fontsize=13, fontweight='bold', color=txt_color)

ax.set_xticks([0, 1, 2])
ax.set_xticklabels(labels, fontsize=9, color=C_DARK)
add_zero_hline(ax)
ax.set_ylabel('DID 系数', fontsize=11, color=C_DARK)
ax.set_title('图 7  创新效率来源拆解图', fontsize=14, fontweight='bold', color=C_DARK)
ax.grid(True, alpha=0.25, axis='y', linestyle='--')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Annotation
ax.text(0.5, -0.18, '效率指标改善 ≈ 研发投入相对增长较慢 − 专利数量相对变化不显著',
        transform=ax.transAxes, ha='center', fontsize=9, fontstyle='italic', color=C_DARK,
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFF8E1', alpha=0.8, edgecolor=C_GOLD))
plt.tight_layout()
save_fig(fig, 'fig07_efficiency_decomp')


# ============================================================
# Figure 8: Heterogeneity Heatmap
# ============================================================
print('Figure 8: Heterogeneity Heatmap')
fig, ax = plt.subplots(figsize=(10.5, 4.8))

het_data = [
    ('高研发基础\n交互项', '发明申请/\n研发支出', 0.2253, 0.0509, 0.0000),
    ('高研发基础\n交互项', '发明授权/\n研发支出', 0.2718, 0.0484, 0.0000),
    ('高研发基础\n交互项', '发明申请/\n研发人员', 0.1368, 0.0534, 0.0104),
    ('高研发基础\n交互项', '发明授权/\n研发人员', 0.1833, 0.0512, 0.0003),
    ('制造业内部\n高研发暴露', '发明申请/\n研发支出', 0.1977, 0.0503, 0.0001),
    ('制造业内部\n高研发暴露', '发明授权/\n研发支出', 0.2445, 0.0476, 0.0000),
    ('制造业内部\n高研发暴露', '发明申请/\n研发人员', 0.1236, 0.0537, 0.0215),
    ('制造业内部\n高研发暴露', '发明授权/\n研发人员', 0.1704, 0.0514, 0.0009),
]

rows = sorted(set(d[0] for d in het_data), reverse=True)
cols = sorted(set(d[1] for d in het_data))
n_rows, n_cols = len(rows), len(cols)

matrix = np.zeros((n_rows, n_cols))
annot = [['' for _ in range(n_cols)] for _ in range(n_rows)]
for row_label, col_label, coef, se, p in het_data:
    ri = rows.index(row_label)
    ci = cols.index(col_label)
    matrix[ri, ci] = coef
    annot[ri][ci] = f'{coef:.3f}\n{fmt_sig(p)}'

im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0.08, vmax=0.30)
for i in range(n_rows):
    for j in range(n_cols):
        val = matrix[i, j]
        txt_color = 'white' if val > 0.22 else 'black'
        ax.text(j, i, annot[i][j], ha='center', va='center', fontsize=11,
                fontweight='bold', color=txt_color)

ax.set_xticks(range(n_cols))
ax.set_xticklabels(cols, fontsize=10)
ax.set_yticks(range(n_rows))
ax.set_yticklabels(rows, fontsize=10)
cbar = plt.colorbar(im, ax=ax, shrink=0.9, pad=0.02)
cbar.set_label('DID 系数', fontsize=10, color=C_DARK)
ax.set_title('图 8  异质性分析结果图', fontsize=14, fontweight='bold', color=C_DARK)
plt.tight_layout()
save_fig(fig, 'fig08_heterogeneity')


# ============================================================
# Figure 9: Baseline vs Stronger FE
# ============================================================
print('Figure 9: Baseline vs Stronger FE')
fig, ax = plt.subplots(figsize=(9, 5.5))
fe_data = [
    ('发明申请/\n研发支出', 0.2637, 0.0616, 0.2552, 0.0635),
    ('发明授权/\n研发支出', 0.2771, 0.0611, 0.2903, 0.0632),
    ('发明申请/\n研发人员', 0.1724, 0.0499, 0.1614, 0.0512),
    ('发明授权/\n研发人员', 0.1858, 0.0491, 0.1965, 0.0506),
]
x = np.arange(len(fe_data))
width = 0.32
for i, (label, bc, bs, sc, ss) in enumerate(fe_data):
    ax.bar(i-width/2, bc, width, yerr=bs*1.96, color=C_BLUE, edgecolor='white', linewidth=0.8,
           capsize=5, alpha=0.85, label='基准模型' if i==0 else '')
    ax.bar(i+width/2, sc, width, yerr=ss*1.96, color=C_PURPLE, edgecolor='white', linewidth=0.8,
           capsize=5, alpha=0.85, hatch='//', label='+Prov×Year' if i==0 else '')
ax.set_xticks(x)
ax.set_xticklabels([d[0] for d in fe_data], fontsize=10, color=C_DARK)
add_zero_hline(ax)
ax.set_ylabel('DID 系数', fontsize=11, color=C_DARK)
ax.set_title('图 9  基准模型与强固定效应模型结果对比图', fontsize=14, fontweight='bold', color=C_DARK)
ax.legend(fontsize=9, frameon=True, fancybox=True, loc='upper right')
ax.grid(True, alpha=0.25, axis='y', linestyle='--')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
save_fig(fig, 'fig09_stronger_fe')


# ============================================================
# Figure 10: Event Study (3-panel)
# ============================================================
print('Figure 10: Event Study')
ed = {
    'A. 发明专利申请': {
        2017: (0.0031, 0.0333), 2018: (-0.0319, 0.0311), 2019: (-0.0142, 0.0302),
        2020: (0.0, 0.0), 2021: (-0.0334, 0.0278), 2022: (-0.0352, 0.0314),
        'color': C_BLUE, 'ylim': (-0.18, 0.12),
    },
    'B. 研发支出': {
        2017: (0.6871, 0.1034), 2018: (0.3962, 0.0774), 2019: (0.2963, 0.0575),
        2020: (0.0, 0.0), 2021: (0.0101, 0.0550), 2022: (-0.0021, 0.0661),
        'color': C_ORANGE, 'ylim': (-0.25, 1.0),
    },
    'C. 创新效率': {
        2017: (-0.6840, 0.1074), 2018: (-0.4281, 0.0829), 2019: (-0.3104, 0.0642),
        2020: (0.0, 0.0), 2021: (-0.0435, 0.0610), 2022: (-0.0330, 0.0724),
        'color': C_GREEN, 'ylim': (-1.0, 0.25),
    },
}

fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))
for ax, (title, data) in zip(axes, ed.items()):
    year_keys = [k for k in data.keys() if isinstance(k, int)]
    py = [y for y in sorted(year_keys) if y != 2020]
    pc = [data[y][0] for y in py]
    ps = [data[y][1] for y in py]
    ci_l = [c - 1.96*s for c, s in zip(pc, ps)]
    ci_h = [c + 1.96*s for c, s in zip(pc, ps)]
    color = data['color']

    ax.errorbar(py, pc, yerr=[np.array(pc)-np.array(ci_l), np.array(ci_h)-np.array(pc)],
                fmt='D-', color=color, capsize=5, markersize=9,
                markerfacecolor='white', markeredgewidth=2.5, linewidth=2.5, label='事件系数')
    ax.plot(2020, 0, 'D', color=C_RED, markersize=12, markerfacecolor=C_RED, label='2020（基准年）')
    add_zero_hline(ax)
    ax.axvline(x=2020.5, color=C_RED, linestyle='--', linewidth=2, alpha=0.7)
    ax.axvspan(2016.5, 2020.5, alpha=0.06, facecolor=C_GRAY)
    ax.set_title(title, fontsize=12, fontweight='bold', color=C_DARK)
    ax.set_xlabel('年份')
    ax.set_xticks([2017, 2018, 2019, 2020, 2021, 2022])
    ax.set_ylim(data['ylim'])
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=8, frameon=True, fancybox=True, loc='upper left')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

fig.suptitle('图 10  事件研究结果图（基准年 = 2020）', fontsize=14, fontweight='bold', color=C_DARK, y=1.02)
plt.tight_layout()
save_fig(fig, 'fig10_event_study')


# ============================================================
# Figure 11: Placebo
# ============================================================
print('Figure 11: Placebo')
fig, ax = plt.subplots(figsize=(8, 5))
pl_data = [
    ('真实政策时点\n2021年', 0.2637, 0.0616, C_GREEN),
    ('假想政策时点\n2019年', 0.2902, 0.0719, C_ORANGE),
    ('假想政策时点\n2020年', 0.3252, 0.0701, C_RED),
]
x_pos = range(len(pl_data))
for i, (label, coef, se, color) in enumerate(pl_data):
    ax.bar(i, coef, yerr=se*1.96, color=color, capsize=6, width=0.55,
           edgecolor='white', linewidth=1, alpha=0.85)
    ax.text(i, coef + 0.025, f'{coef:+.4f}', ha='center', fontsize=11, fontweight='bold', color=C_DARK)
ax.set_xticks(x_pos)
ax.set_xticklabels([d[0] for d in pl_data], fontsize=10, color=C_DARK)
add_zero_hline(ax)
ax.set_ylabel('DID 系数 (eff_apply_rd_10k)', fontsize=11, color=C_DARK)
ax.set_title('图 11  安慰剂检验结果图', fontsize=14, fontweight='bold', color=C_DARK)
ax.grid(True, alpha=0.25, axis='y', linestyle='--')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

ax.annotate('假想时点也显著为正\n→ 效率差距在政策前\n   已存在收敛趋势',
            xy=(1.9, 0.28), fontsize=9.5, color=C_RED,
            bbox=dict(boxstyle='round', facecolor='#FFF0F0', alpha=0.85, edgecolor=C_RED))
plt.tight_layout()
save_fig(fig, 'fig11_placebo')


# ============================================================
# Figure 12: Policy Timeline
# ============================================================
print('Figure 12: Policy Timeline')
fig, ax = plt.subplots(figsize=(11.5, 3.8))

periods = [
    (2016.5, 2018, '#F2F2F2', '50%'),
    (2018, 2021, '#DCE6F1', '75%'),
    (2021, 2023, '#B8CCE4', '制造业 100%'),
    (2023, 2025.5, '#95B3D7', '全行业 100%'),
]
for start, end, color, label in periods:
    ax.axvspan(start, end, alpha=0.55, facecolor=color, edgecolor='#AAAAAA', linewidth=0.5)
    mid = (start+end)/2
    ax.text(mid, 0.62, label, ha='center', va='center', fontsize=10, fontweight='bold', color=C_DARK)

# DID window highlight
ax.axvspan(2021, 2023, alpha=0.15, facecolor=C_RED)
ax.annotate('DID识别窗口\n制造业 vs 非制造业\n差异化激励',
            xy=(2022, 0.32), fontsize=9.5, ha='center', fontweight='bold', color=C_RED,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor=C_RED, linewidth=1.5))

# Policy markers
policies = [
    (2018, '财税〔2018〕99号\n加计扣除75%', C_BLUE),
    (2021, '公告2021年第13号\n制造业100%', C_RED),
    (2022, '公告2022年第16号\n科小100%', C_ORANGE),
    (2023, '公告2023年第7号\n全行业100%', C_GREEN),
    (2023.8, '公告2023年第44号\nIC/母机120%', C_PURPLE),
]
for year, text, color in policies:
    ax.axvline(x=year, color=color, linestyle='-', linewidth=2, alpha=0.8)
    ax.text(year, 0.16, text, ha='center', fontsize=7.5, fontweight='bold', color=color,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor=color))

ax.set_xlim(2016, 2026)
ax.set_ylim(0, 1.05)
ax.set_yticks([])
ax.set_xlabel('年份', fontsize=11, color=C_DARK)
ax.set_title('图 12  研发费用加计扣除政策时间轴', fontsize=14, fontweight='bold', color=C_DARK)
for spine in ['top', 'right', 'left']:
    ax.spines[spine].set_visible(False)
plt.tight_layout()
save_fig(fig, 'fig12_policy_timeline')


# ============================================================
print('\nAll 12 PPT-quality figures generated in:', OUTPUT_DIR)
for f in sorted(os.listdir(OUTPUT_DIR)):
    size_kb = os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024
    print(f'  {f:50s} {size_kb:8.0f} KB')
