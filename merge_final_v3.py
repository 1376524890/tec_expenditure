"""
重建科技自主创新政策实证主面板 v3
==================================
严格控制: 所有表在合并前必须处理成唯一 stock_code-year
财务数据: 只保留合并报表(A)、12月31日口径
"""
import pandas as pd
import numpy as np
from pathlib import Path
import os, warnings

warnings.filterwarnings("ignore")

EXTRACT = Path("data/_extract")
OUT = Path("data")

# ============================================================
# 0. 工具函数
# ============================================================
def std_code(col):
    return col.astype(str).str.replace(".0", "", regex=False).str.zfill(6)

def std_year_from_date(col):
    """从日期列提取年份, 过滤无效日期"""
    d = pd.to_datetime(col, errors="coerce", format="mixed")
    return d.dt.year, d.dt.month, d.dt.day

def read_xlsx(keyword):
    for d in sorted(os.listdir(EXTRACT)):
        dp = EXTRACT / d
        if not dp.is_dir(): continue
        for f in os.listdir(dp):
            if f.endswith('.xlsx') and keyword.lower() in f.lower():
                return pd.read_excel(dp / f)
    raise FileNotFoundError(f"No xlsx with '{keyword}'")

def dedup_check(df, name):
    """检查并报告 stock_code-year 重复"""
    n = len(df)
    dup = df.duplicated(subset=["stock_code", "year"]).sum()
    firms = df["stock_code"].nunique()
    years = df["year"].nunique()
    print(f"  {name}: {n:,} rows, {firms:,} firms × {years} years, "
          f"dup={dup}, unique={n-dup:,}")
    if dup > 0:
        print(f"  *** WARNING: {dup} duplicates in {name}! ***")
    return dup

# ============================================================
# 1. 利润表 — 基准主表 (只保留合并报表, 12月31日)
# ============================================================
print("=" * 80)
print("1. 利润表 (FS_Comins) — 基准主表")
print("=" * 80)

inc = read_xlsx("FS_Comins")
inc["_year"], inc["_month"], inc["_day"] = std_year_from_date(inc["Accper"])

# 过滤: 合并报表(A), 12月31日, 有效年份
inc_A = inc[(inc["Typrep"] == "A") & (inc["_month"] == 12) & (inc["_day"] == 31)].copy()
inc_A["stock_code"] = std_code(inc_A["Stkcd"])
inc_A["year"] = inc_A["_year"].astype("Int64")

# 去重
inc_A = inc_A.drop_duplicates(subset=["stock_code", "year"], keep="first")

base = inc_A[["stock_code", "year", "B001101000", "B001000000", "B002100000"]].copy()
base.columns = ["stock_code", "year", "revenue", "profit_before_tax", "income_tax_expense"]
for c in ["revenue", "profit_before_tax", "income_tax_expense"]:
    base[c] = pd.to_numeric(base[c], errors="coerce")

print(f"  过滤前: {len(inc):,}")
print(f"  A+Dec31: {len(inc_A):,}")
dedup_check(base, "利润表-base")


# ============================================================
# 2. 资产负债表 (FS_Combas) — 合并, 12月31日
# ============================================================
print("\n" + "=" * 80)
print("2. 资产负债表 (FS_Combas)")
print("=" * 80)

bs = read_xlsx("FS_Combas")
bs["_year"], bs["_month"], bs["_day"] = std_year_from_date(bs["Accper"])
bs_A = bs[(bs["Typrep"] == "A") & (bs["_month"] == 12) & (bs["_day"] == 31)].copy()
bs_A["stock_code"] = std_code(bs_A["Stkcd"])
bs_A["year"] = bs_A["_year"].astype("Int64")
bs_A["total_assets"] = pd.to_numeric(bs_A["A001000000"], errors="coerce")
bs_A = bs_A.drop_duplicates(subset=["stock_code", "year"], keep="first")
bs_A = bs_A[["stock_code", "year", "total_assets"]]
dedup_check(bs_A, "资产负债表")

base = base.merge(bs_A, on=["stock_code", "year"], how="left")


# ============================================================
# 3. 现金流量表 (FS_Comscfd) — 合并, 12月31日
# ============================================================
print("\n" + "=" * 80)
print("3. 现金流量表 (FS_Comscfd)")
print("=" * 80)

cf = read_xlsx("FS_Comscfd")
cf["_year"], cf["_month"], cf["_day"] = std_year_from_date(cf["Accper"])
cf_A = cf[(cf["Typrep"] == "A") & (cf["_month"] == 12) & (cf["_day"] == 31)].copy()
cf_A["stock_code"] = std_code(cf_A["Stkcd"])
cf_A["year"] = cf_A["_year"].astype("Int64")
cf_A["cf_inflow"] = pd.to_numeric(cf_A["C001100000"], errors="coerce")
cf_A["cf_outflow"] = pd.to_numeric(cf_A["C001200000"], errors="coerce")
cf_A["cashflow"] = cf_A["cf_inflow"] - cf_A["cf_outflow"]
cf_A = cf_A.drop_duplicates(subset=["stock_code", "year"], keep="first")
cf_A = cf_A[["stock_code", "year", "cashflow"]]
dedup_check(cf_A, "现金流量表")

base = base.merge(cf_A, on=["stock_code", "year"], how="left")
print(f"  base after merge: {len(base):,}")


# ============================================================
# 4. 基本信息表 (STK_LISTEDCOINFOANL) — 省份, 行业
# ============================================================
print("\n" + "=" * 80)
print("4. 基本信息表 (STK_LISTEDCOINFOANL)")
print("=" * 80)

info = read_xlsx("STK_LISTEDCOINFOANL")
info["_year"], _, _ = std_year_from_date(info["EndDate"])
info["stock_code"] = std_code(info["Symbol"])
info["year"] = info["_year"].astype("Int64")

# 按年去重
info_sel = info[["stock_code", "year", "PROVINCE", "IndustryCode", "IndustryName",
                  "EstablishDate", "LISTINGDATE"]].copy()
info_sel = info_sel.drop_duplicates(subset=["stock_code", "year"], keep="first")
info_sel.columns = ["stock_code", "year", "province", "industry_code", "industry_name",
                     "establish_date", "listing_date"]
dedup_check(info_sel, "基本信息表")

base = base.merge(info_sel, on=["stock_code", "year"], how="left")
print(f"  province 覆盖率: {base['province'].notna().mean():.1%}")


# ============================================================
# 5. 专利表 (PT_LCDOMFORAPPLY) — 聚合到 stock_code-year
# ============================================================
print("\n" + "=" * 80)
print("5. 专利表 (PT_LCDOMFORAPPLY)")
print("=" * 80)

pat = read_xlsx("PT_LCDOMFORAPPLY")
pat["_year"], _, _ = std_year_from_date(pat["EndDate"])
pat["stock_code"] = std_code(pat["Symbol"])
pat["year"] = pat["_year"].astype("Int64")

# 只取国内专利 Area=1
pat["_area"] = pd.to_numeric(pat["Area"], errors="coerce")
pat = pat[pat["_area"] == 1].copy()

# 按 stock_code-year-ApplyType 聚合
pat_agg = pat.pivot_table(
    index=["stock_code", "year"],
    columns="ApplyType",
    values=["Invention", "Patents"],
    aggfunc="sum"
).fillna(0)

# 展平列
pat_agg.columns = [f"{v}_{a}" for v, a in pat_agg.columns]
pat_agg = pat_agg.reset_index()

# 重命名
RENAME_PAT = {
    "Invention_已申请": "invention_apply",
    "Invention_已授权": "invention_grant",
    "Patents_已申请": "patent_apply_total",
    "Patents_已授权": "patent_grant_total",
}
pat_agg = pat_agg.rename(columns=RENAME_PAT)
# 只保留需要的列
pat_cols = ["stock_code", "year"] + [c for c in RENAME_PAT.values() if c in pat_agg.columns]
pat_agg = pat_agg[[c for c in pat_cols if c in pat_agg.columns]]
dedup_check(pat_agg, "专利表(聚合后)")

base = base.merge(pat_agg, on=["stock_code", "year"], how="left")
# 无专利 = 0
for c in pat_agg.columns:
    if c not in ["stock_code", "year"] and c in base.columns:
        base[c] = base[c].fillna(0)


# ============================================================
# 6. 研发投入表 (PT_LCRDSPENDING) — 唯一化
# ============================================================
print("\n" + "=" * 80)
print("6. 研发投入表 (PT_LCRDSPENDING)")
print("=" * 80)

rd = read_xlsx("PT_LCRDSPENDING")
rd["_year"], _, _ = std_year_from_date(rd["EndDate"])
rd["stock_code"] = std_code(rd["Symbol"])
rd["year"] = rd["_year"].astype("Int64")

rd_sel = rd[["stock_code", "year", "RDPerson", "RDPersonRatio",
               "RDSpendSum", "RDSpendSumRatio"]].copy()
rd_sel = rd_sel.drop_duplicates(subset=["stock_code", "year"], keep="first")
for c in ["RDPerson", "RDPersonRatio", "RDSpendSum", "RDSpendSumRatio"]:
    rd_sel[c] = pd.to_numeric(rd_sel[c], errors="coerce")
rd_sel.columns = ["stock_code", "year", "rd_staff", "rd_staff_ratio",
                   "rd_expense", "rd_intensity_raw"]
dedup_check(rd_sel, "研发投入表")

base = base.merge(rd_sel, on=["stock_code", "year"], how="left")


# ============================================================
# 7. 政府补助表 (FN_FN056) — 聚合到 stock_code-year
# ============================================================
print("\n" + "=" * 80)
print("7. 政府补助表 (FN_FN056)")
print("=" * 80)

sub = read_xlsx("FN_FN056")
sub["_year"], _, _ = std_year_from_date(sub["Accper"])
sub["stock_code"] = std_code(sub["Stkcd"])
sub["year"] = sub["_year"].astype("Int64")
sub["_amount"] = pd.to_numeric(sub["Fn05602"], errors="coerce")
sub["_typrep"] = sub["Typrep"].astype(str).str.strip()

# 只取合并报表
sub_A = sub[sub["_typrep"].isin(["1", "1.0"])].copy()

# 研发补助关键词
RD_KW = "研发|科技|创新|高新|专利|技术|R&D|科研|发明|技改|技术改造|知识产权|产业化|新产品|新工艺|软件|信息化|数字化|智能|实验室|工程中心|技术中心|研究院"
sub_A["_is_rd"] = sub_A["Fn05601"].astype(str).str.contains(RD_KW, na=False)

# 聚合
sub_agg = sub_A.groupby(["stock_code", "year"]).agg(
    total_subsidy=("_amount", "sum"),
    rd_subsidy=("_amount", lambda x: x[sub_A.loc[x.index, "_is_rd"]].sum()),
    subsidy_count=("_amount", "count"),
    rd_subsidy_count=("_is_rd", "sum"),
).reset_index()
dedup_check(sub_agg, "政府补助表(聚合后)")

base = base.merge(sub_agg, on=["stock_code", "year"], how="left")
# No subsidy = 0
for c in ["total_subsidy", "rd_subsidy", "subsidy_count", "rd_subsidy_count"]:
    if c in base.columns:
        base[c] = base[c].fillna(0)


# ============================================================
# 8. 实际控制人表 (HLD_Contrshr) — 构造 SOE
# ============================================================
print("\n" + "=" * 80)
print("8. 实际控制人表 (HLD_Contrshr)")
print("=" * 80)

ctr = read_xlsx("HLD_Contrshr")
ctr["_year"], _, _ = std_year_from_date(ctr["Reptdt"])
ctr["stock_code"] = std_code(ctr["Stkcd"])
ctr["year"] = ctr["_year"].astype("Int64")

# 取每个 stock_code-year 的第一条控制人记录
ctr_sel = ctr[["stock_code", "year", "S0702b"]].copy()
ctr_sel = ctr_sel.drop_duplicates(subset=["stock_code", "year"], keep="first")
ctr_sel.columns = ["stock_code", "year", "controller_type"]

# 构造 SOE: controller_type 以 "1" 开头 = 国有
ctr_sel["soe"] = ctr_sel["controller_type"].astype(str).str.startswith("1").astype(int)
ctr_sel = ctr_sel[["stock_code", "year", "soe", "controller_type"]]
dedup_check(ctr_sel, "控制人表")

base = base.merge(ctr_sel[["stock_code", "year", "soe"]], on=["stock_code", "year"], how="left")
print(f"  soe=1 (国有): {(base['soe']==1).sum():,}")
print(f"  soe=0 (非国有): {(base['soe']==0).sum():,}")
print(f"  soe NaN: {base['soe'].isna().sum():,}")


# ============================================================
# 9. 构造派生变量
# ============================================================
print("\n" + "=" * 80)
print("9. 构造派生变量")
print("=" * 80)

# manufacturing
base["manufacturing"] = 0
mask_code = base["industry_code"].notna()
base.loc[mask_code, "manufacturing"] = (
    base.loc[mask_code, "industry_code"].astype(str).str.startswith("C")
).astype(int)
# 补充 industry_name 包含"制造"
mask_name = (base["manufacturing"] == 0) & base["industry_name"].notna()
base.loc[mask_name, "manufacturing"] = (
    base.loc[mask_name, "industry_name"].astype(str).str.contains("制造", na=False)
).astype(int)

# 财务比率
base["ln_assets"] = np.log1p(base["total_assets"].fillna(0).clip(lower=0))
base["roa"] = np.where(
    (base["profit_before_tax"].notna()) & (base["total_assets"].notna()) & (base["total_assets"] > 0),
    base["profit_before_tax"] / base["total_assets"],
    np.nan
)
# lev: 我们没有 total_liability, 用 (total_assets - equity)/total_assets 不可得
# 退而求其次: 用 cashflow 方向作为近似控制变量. lev 报告中标注为不可得.
# 如果后续 CSMAR 下载负债表可以补充.
# 暂时构造 placeholder: lev 缺失, 用 cashflow/total_assets 作为补充控制
base["cashflow_ratio"] = np.where(
    (base["cashflow"].notna()) & (base["total_assets"].notna()) & (base["total_assets"] > 0),
    base["cashflow"] / base["total_assets"],
    np.nan
)

# Firm age
if "establish_date" in base.columns:
    est = pd.to_datetime(base["establish_date"], errors="coerce", format="mixed").dt.year
    base["firm_age"] = base["year"].astype(float) - est
    base["firm_age"] = base["firm_age"].clip(lower=0)

# RD intensity (计算口径)
base["rd_intensity"] = np.where(
    (base["rd_expense"].notna()) & (base["revenue"].notna()) & (base["revenue"] > 0),
    base["rd_expense"] / base["revenue"] * 100,
    np.nan
)

# Policy variables
base["post2019"] = (base["year"] >= 2019).astype(int)
base["post2020"] = (base["year"] >= 2020).astype(int)
base["post2021"] = (base["year"] >= 2021).astype(int)
base["post2022"] = (base["year"] >= 2022).astype(int)
base["post2023"] = (base["year"] >= 2023).astype(int)

base["manufacturing_post2019"] = base["manufacturing"] * base["post2019"]
base["manufacturing_post2020"] = base["manufacturing"] * base["post2020"]
base["manufacturing_post2021"] = base["manufacturing"] * base["post2021"]
base["manufacturing_post2022"] = base["manufacturing"] * base["post2022"]

# R&D deduction rate
# 2016-2017: 50% all
# 2018-2020: 75% all
# 2021-2022: manufacturing 100%, non-mfg 75%
# 2023+: 100% all
base["rd_deduction_rate"] = 0.5
base.loc[base["year"].between(2018, 2020), "rd_deduction_rate"] = 0.75
base.loc[(base["year"] >= 2021) & (base["year"] <= 2022) & (base["manufacturing"] == 1), "rd_deduction_rate"] = 1.0
base.loc[(base["year"] >= 2021) & (base["year"] <= 2022) & (base["manufacturing"] == 0), "rd_deduction_rate"] = 0.75
base.loc[base["year"] >= 2023, "rd_deduction_rate"] = 1.0

# tax_saving_est (估算, 非真实税务数据)
base["tax_saving_est"] = base["rd_expense"].fillna(0).clip(lower=0) * base["rd_deduction_rate"] * 0.25

# Log transformations
for col in ["invention_apply", "invention_grant", "patent_apply_total", "patent_grant_total",
             "rd_expense", "rd_staff", "rd_subsidy", "total_subsidy", "tax_saving_est"]:
    if col in base.columns:
        base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0).clip(lower=0)
        base[f"ln_{col}"] = np.log1p(base[col])

# Pre-policy average RD intensity (for policy exposure)
pre_rd = base[base["year"].between(2017, 2020)].groupby("stock_code")["rd_intensity"].mean().reset_index()
pre_rd.columns = ["stock_code", "pre_rd_intensity"]
base = base.merge(pre_rd, on="stock_code", how="left")
base["policy_exposure"] = base["pre_rd_intensity"] * base["manufacturing"] * base["post2021"]


# ============================================================
# 10. Winsorize
# ============================================================
print("\n" + "=" * 80)
print("10. Winsorize")
print("=" * 80)

WINSOR = [
    "rd_intensity", "roa", "cashflow_ratio", "rd_staff_ratio",
    "ln_invention_apply", "ln_invention_grant", "ln_patent_apply_total", "ln_patent_grant_total",
    "ln_rd_expense", "ln_rd_staff", "ln_rd_subsidy", "ln_total_subsidy", "ln_tax_saving_est",
    "ln_assets",
]
for v in WINSOR:
    if v in base.columns and base[v].notna().sum() > 100:
        lo, hi = base[v].quantile([0.01, 0.99])
        if lo < hi:
            base[v] = base[v].clip(lo, hi)

# ============================================================
# 11. 最终检查
# ============================================================
print("\n" + "=" * 80)
print("11. 最终数据结构检查")
print("=" * 80)

# 全样本
base = base.sort_values(["stock_code", "year"]).reset_index(drop=True)
dup_all = base.duplicated(subset=["stock_code", "year"]).sum()
print(f"  全样本: {len(base):,} rows, {base['stock_code'].nunique():,} firms")
print(f"  stock_code-year 重复: {dup_all} (必须为0)")

# 各子样本
for yr_start, yr_end, label in [
    (2016, 2022, "2016-2022"),
    (2017, 2022, "2017-2022 (基准)"),
    (2017, 2024, "2017-2024"),
    (2017, 2020, "2017-2020 (安慰剂)"),
]:
    s = base[base["year"].between(yr_start, yr_end)]
    dup = s.duplicated(subset=["stock_code", "year"]).sum()
    max_obs = s.groupby("stock_code").size().max()
    expected_max = yr_end - yr_start + 1
    print(f"  {label}: {len(s):,} rows, {s['stock_code'].nunique():,} firms, "
          f"dup={dup}, max_obs/firm={max_obs} (expected ≤{expected_max})")

# 检查: 是否每家企业最多N条
for yr_start, yr_end, label in [(2017, 2022, "2017-2022")]:
    s = base[base["year"].between(yr_start, yr_end)]
    max_obs = s.groupby("stock_code").size().max()
    print(f"\n  关键检查: {label} 样本")
    print(f"    最大观测/企业: {max_obs} (必须 ≤ {yr_end - yr_start + 1})")
    firms_with_too_many = (s.groupby("stock_code").size() > yr_end - yr_start + 1).sum()
    print(f"    超过{yr_end - yr_start + 1}条的企业: {firms_with_too_many} (必须为0)")

# 覆盖率
print(f"\n  关键变量覆盖率 (2017-2022):")
s = base[base["year"].between(2017, 2022)]
for v in ["invention_apply", "invention_grant", "patent_apply_total", "patent_grant_total",
           "rd_expense", "rd_intensity", "rd_staff", "rd_staff_ratio",
           "revenue", "profit_before_tax", "income_tax_expense",
           "total_assets", "cashflow", "ln_assets", "roa",
           "soe", "province", "manufacturing", "firm_age",
           "total_subsidy", "rd_subsidy"]:
    if v in s.columns:
        pct = s[v].notna().mean()
        print(f"    {v:25s}: {pct:.1%}")

# 保存
base.to_csv(OUT / "firm_panel_v3.csv", index=False, encoding="utf-8-sig")
base.to_excel(OUT / "firm_panel_v3.xlsx", index=False)

print(f"\n  已保存: data/firm_panel_v3.csv ({len(base):,} × {len(base.columns)})")
print(f"  已保存: data/firm_panel_v3.xlsx")
print("\nDONE")
