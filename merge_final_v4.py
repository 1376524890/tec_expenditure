"""
v4: 合并省级财政科技支出数据到企业面板
======================================
在 firm_panel_v3.csv 基础上，合并 provincial_panel_full.csv 的省级变量，
构造省级财政科技支出与企业 DID 的交互项。

输入: data/firm_panel_v3.csv, data/provincial_panel_full.csv
输出: data/firm_panel_v4.csv
"""
import pandas as pd
import numpy as np
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

OUT = Path("data")

# ============================================================
# 1. 读取企业面板
# ============================================================
print("=" * 80)
print("1. 读取企业面板 v3")
print("=" * 80)

firm = pd.read_csv(OUT / "firm_panel_v3.csv")
firm["stock_code"] = firm["stock_code"].astype(str).str.zfill(6)
firm["year"] = firm["year"].astype(int)
print(f"  企业面板: {len(firm):,} rows × {firm['stock_code'].nunique():,} firms")
print(f"  年份: {firm['year'].min()}-{firm['year'].max()}")
print(f"  province 覆盖率: {firm['province'].notna().mean():.1%}")

# ============================================================
# 2. 清洗省份名称
# ============================================================
print("\n" + "=" * 80)
print("2. 清洗省份名称")
print("=" * 80)

# 去除零宽字符
firm["province"] = firm["province"].astype(str).str.replace("​", "", regex=False).str.strip()

# 省份名称映射
PROVINCE_FIX = {
    "新疆省": "新疆维吾尔自治区",
    "香港特别行政区": None,
    "开曼群岛": None,
    "": None,
    "nan": None,
}
firm["province_clean"] = firm["province"].replace(PROVINCE_FIX)
firm.loc[firm["province_clean"].isna(), "province_clean"] = None
# 不在大陆31省列表中的设为None
MAINLAND = [
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省", "上海市", "江苏省",
    "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区",
    "海南省", "重庆市", "四川省", "贵州省", "云南省",
    "西藏自治区", "陕西省", "甘肃省", "青海省", "宁夏回族自治区",
    "新疆维吾尔自治区",
]
firm.loc[~firm["province_clean"].isin(MAINLAND), "province_clean"] = None

before = firm["province"].notna().mean()
after = firm["province_clean"].notna().mean()
print(f"  清洗前: {before:.1%}, 清洗后: {after:.1%}")
print(f"  映射: '新疆省'→'新疆维吾尔自治区', 移除零宽字符, 剔除非大陆注册地")

# ============================================================
# 3. 读取省级面板并合并
# ============================================================
print("\n" + "=" * 80)
print("3. 合并省级面板数据")
print("=" * 80)

prov = pd.read_csv(OUT / "provincial_panel_full.csv")
prov["year"] = prov["year"].astype(int)
print(f"  省级面板: {len(prov):,} rows × {prov['province'].nunique():,} provinces")
print(f"  年份: {prov['year'].min()}-{prov['year'].max()}")

# 选择合并的省级变量
PROV_VARS = [
    "province", "year",
    "gdp",                    # 省级GDP
    "fiscal_expenditure",     # 一般公共预算支出
    "fiscal_sci_tech_exp",    # 财政科技支出
    "sci_tech_exp_ratio",     # 财政科技支出占比
    "province_rd_exp",        # 省R&D经费内部支出
    "province_rd_intensity",  # 省R&D投入强度
    "tech_market_turnover",   # 技术市场成交额
]

prov_sel = prov[[c for c in PROV_VARS if c in prov.columns]].copy()
prov_sel = prov_sel.rename(columns={
    "gdp": "province_gdp",
    "fiscal_expenditure": "province_fiscal_exp",
    "fiscal_sci_tech_exp": "province_sci_tech_exp",
    "sci_tech_exp_ratio": "province_sci_tech_ratio",
    "province_rd_exp": "province_rd_expenditure",
    "province_rd_intensity": "province_rd_intensity",
    "tech_market_turnover": "province_tech_market",
})

# 对数化省级变量
for v in ["province_gdp", "province_fiscal_exp", "province_sci_tech_exp",
           "province_rd_expenditure", "province_tech_market"]:
    if v in prov_sel.columns:
        prov_sel[v] = pd.to_numeric(prov_sel[v], errors="coerce")
        prov_sel[f"ln_{v}"] = np.log1p(prov_sel[v].clip(lower=0))

# Merge
firm = firm.merge(prov_sel, left_on=["province_clean", "year"],
                  right_on=["province", "year"], how="left",
                  suffixes=("", "_prov"))

# 去掉省级面板自带的 province 列（已有 province_clean）
if "province_prov" in firm.columns:
    firm = firm.drop(columns=["province_prov"])

print(f"  合并后省级变量覆盖率 (2017-2024):")
s = firm[firm["year"].between(2017, 2024)]
for v in ["province_gdp", "province_sci_tech_exp", "province_sci_tech_ratio",
           "province_rd_expenditure", "province_rd_intensity"]:
    if v in s.columns:
        print(f"    {v}: {s[v].notna().mean():.1%}")

# ============================================================
# 4. 同步更新 2024 年缺失的 fiscal_sci_tech_exp
# ============================================================
print("\n" + "=" * 80)
print("4. 处理 2024 年省级财政科技支出缺失")
print("=" * 80)

# 2024 年 fiscal_sci_tech_exp 全省份缺失
# 方案: 用 2023 年值填充 (假设财政科技支出占比年度间高度稳定)
print("  2024 年 province_sci_tech_exp 全省份缺失, 用 2023 年值填充")
for v in ["province_sci_tech_exp", "ln_province_sci_tech_exp",
           "province_sci_tech_ratio"]:
    if v in firm.columns:
        firm[v] = firm.groupby("province_clean")[v].transform(
            lambda x: x.ffill()
        )
        firm[v] = firm.groupby("province_clean")[v].transform(
            lambda x: x.bfill()
        )

s2024 = firm[firm["year"] == 2024]
if "province_sci_tech_exp" in s2024.columns:
    print(f"  2024 年 province_sci_tech_exp 填充后覆盖率: {s2024['province_sci_tech_exp'].notna().mean():.1%}")

# ============================================================
# 5. 构造省级财政交互项
# ============================================================
print("\n" + "=" * 80)
print("5. 构造省级财政 × DID 交互项")
print("=" * 80)

# 核心交互: DID × 省级财政科技支出强度
if "province_sci_tech_ratio" in firm.columns:
    # 按中位数分组: 高/低财政科技支出强度省份
    median_ratio = firm.loc[firm["year"].between(2017, 2020), "province_sci_tech_ratio"].median()
    firm["high_sci_tech_province"] = (firm["province_sci_tech_ratio"] > median_ratio).astype(int)
    print(f"  财政科技支出占比中位数 (2017-2020): {median_ratio:.2f}%")
    print(f"  高支出省份数: {firm['high_sci_tech_province'].nunique()}")

    # 交互项: DID × 连续省级财政强度
    firm["did_x_prov_sci_tech"] = (
        firm["manufacturing_post2021"] * firm["province_sci_tech_ratio"]
    )

    # 交互项: DID × 高财政科技支出省份 (三重差分 style)
    firm["did_x_high_sci_prov"] = (
        firm["manufacturing_post2021"] * firm["high_sci_tech_province"]
    )

# 交互: DID × 省级 R&D 经费强度
if "province_rd_intensity" in firm.columns:
    firm["did_x_prov_rd_intensity"] = (
        firm["manufacturing_post2021"] * firm["province_rd_intensity"]
    )

# 交互: DID × ln(省级财政科技支出)
if "ln_province_sci_tech_exp" in firm.columns:
    firm["did_x_ln_prov_sci"] = (
        firm["manufacturing_post2021"] * firm["ln_province_sci_tech_exp"]
    )

print("  构造交互项:")
for c in ["did_x_prov_sci_tech", "did_x_high_sci_prov",
           "did_x_prov_rd_intensity", "did_x_ln_prov_sci"]:
    if c in firm.columns:
        n = firm[c].notna().sum()
        print(f"    {c}: {n:,} non-null, mean={firm[c].mean():.3f}")

# ============================================================
# 6. 补充 provincial panel 中特有的因变量（省级专利等）
# ============================================================
print("\n" + "=" * 80)
print("6. 检查并补充省级创新变量")
print("=" * 80)

# 省级面板中有省级专利数据，可作为地区创新环境的控制变量
for v in ["invention_apply", "invention_grant", "patent_apply_total", "patent_grant_total"]:
    prov_v = f"province_{v}"
    if v in prov.columns:
        # 已在 provincial_panel 中但未选入 PROV_VARS
        pass  # 这些实际上是省级汇总数据，可能与企业级变量混淆，暂不合并

print("  跳过省级专利汇总（避免与企业级变量混淆）")

# ============================================================
# 7. 保存
# ============================================================
print("\n" + "=" * 80)
print("7. 保存 v4 面板")
print("=" * 80)

# 检查样本
for yr_start, yr_end, label in [
    (2017, 2022, "2017-2022 (v3基准)"),
    (2017, 2024, "2017-2024 (v4扩展)"),
    (2016, 2022, "2016-2022"),
]:
    s = firm[firm["year"].between(yr_start, yr_end)]
    print(f"  {label}: {len(s):,} obs × {s['stock_code'].nunique():,} firms, "
          f"mfg={s['manufacturing'].mean():.1%}")

# 关键变量覆盖率 (2017-2024)
print(f"\n  关键变量覆盖率 (2017-2024):")
s = firm[firm["year"].between(2017, 2024)]
for v in ["province_sci_tech_exp", "province_sci_tech_ratio",
           "province_rd_expenditure", "province_rd_intensity",
           "did_x_prov_sci_tech", "did_x_high_sci_prov"]:
    if v in s.columns:
        print(f"    {v}: {s[v].notna().mean():.1%}")

firm.to_csv(OUT / "firm_panel_v4.csv", index=False, encoding="utf-8-sig")
firm.to_excel(OUT / "firm_panel_v4.xlsx", index=False)

print(f"\n  已保存: data/firm_panel_v4.csv ({len(firm):,} × {len(firm.columns)})")
print("DONE: merge_final_v4")
