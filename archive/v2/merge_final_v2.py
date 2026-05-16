"""
重建科技自主创新政策实证主面板
==============================
从 8 个 CSMAR 新表合并且构造所有变量。
不再使用 firm_panel_final.csv 作为最终数据。

输入: data/_extract/ 下 8 个 ZIP 解压后的 .xlsx 文件
输出: data/firm_panel_v2.csv, data/firm_panel_v2.xlsx
"""
import pandas as pd
import numpy as np
from pathlib import Path
import os, re, warnings

warnings.filterwarnings("ignore")

EXTRACT = Path("data/_extract")
OUT_DIR = Path("data")

# ============================================================
# 0. 读取所有表
# ============================================================

def read_table(filename_keyword):
    """从 _extract 目录的子目录中读取匹配关键词的 xlsx"""
    for d in sorted(os.listdir(EXTRACT)):
        dpath = EXTRACT / d
        if not dpath.is_dir():
            continue
        for f in os.listdir(dpath):
            if f.endswith('.xlsx') and filename_keyword.lower() in f.lower():
                df = pd.read_excel(dpath / f)
                print(f"  读取: {f} ({len(df):,} rows)")
                return df
    raise FileNotFoundError(f"未找到包含 '{filename_keyword}' 的 xlsx")

print("=" * 80)
print("0. 读取 8 个 CSMAR 表")
print("=" * 80)

info    = read_table("STK_LISTEDCOINFOANL")       # 基本信息
ctr     = read_table("HLD_Contrshr")               # 控制人
inc     = read_table("FS_Comins")                  # 利润表
pat     = read_table("PT_LCDOMFORAPPLY")           # 专利
rd      = read_table("PT_LCRDSPENDING")            # 研发投入
sub     = read_table("FN_FN056")                   # 政府补助
bs      = read_table("FS_Combas")                  # 资产负债表
cf      = read_table("FS_Comscfd")                 # 现金流量表


# ============================================================
# 1. 标准化函数
# ============================================================

def std_code(col):
    """统一为 6 位字符串 stock_code"""
    return col.astype(str).str.replace(".0", "", regex=False).str.zfill(6)

def std_year(col):
    """统一提取年份"""
    return pd.to_datetime(col, errors="coerce", format="mixed").dt.year


# ============================================================
# 2. 构建主表 (以利润表合并报表为基)
# ============================================================
print("\n" + "=" * 80)
print("2. 构建主表")
print("=" * 80)

# 2a. 利润表 — 只取合并报表
inc["_year"] = std_year(inc["Accper"])
inc["stock_code"] = std_code(inc["Stkcd"])
inc_A = inc[inc["Typrep"] == "A"].copy()
print(f"  利润表合并报表: {len(inc_A):,} rows (2019-2024: {inc_A['_year'].between(2019,2024).sum():,})")

base = inc_A[["stock_code", "_year", "B001101000", "B001000000", "B002100000"]].copy()
base.columns = ["stock_code", "year", "revenue", "profit_before_tax", "income_tax_expense"]
for c in ["revenue", "profit_before_tax", "income_tax_expense"]:
    base[c] = pd.to_numeric(base[c], errors="coerce")

# 构造 ETR
base["etr"] = np.where(
    (base["profit_before_tax"] > 0) & (base["income_tax_expense"].notna()),
    base["income_tax_expense"] / base["profit_before_tax"].clip(lower=0.01),
    np.nan
)
# Winsorize ETR to [0, 1]
base["etr"] = base["etr"].clip(0, 1)

print(f"  主表 base: {len(base):,} stock_code×year pairs")


# ============================================================
# 3. 合并省份+行业 (STK_LISTEDCOINFOANL)
# ============================================================
print("\n" + "=" * 80)
print("3. 合并省份、行业、公司基本信息")
print("=" * 80)

info["_year"] = std_year(info["EndDate"])
info["stock_code"] = std_code(info["Symbol"])

# 只保留需要的列并去重 (一个 stock_code×year 可能多条)
info_cols = ["stock_code", "_year", "PROVINCE", "PROVINCECODE", "CITY", "CITYCODE",
             "IndustryCode", "IndustryName", "EstablishDate", "LISTINGDATE"]
info_sel = info[info_cols].copy()
info_sel = info_sel.drop_duplicates(subset=["stock_code", "_year"], keep="first")
info_sel.columns = [c if c in ["stock_code"] else
                    "province" if c == "PROVINCE" else
                    "province_code" if c == "PROVINCECODE" else
                    "city" if c == "CITY" else
                    "city_code" if c == "CITYCODE" else
                    "industry_code" if c == "IndustryCode" else
                    "industry_name" if c == "IndustryName" else
                    "establish_date" if c == "EstablishDate" else
                    "listing_date" if c == "LISTINGDATE" else
                    c for c in info_sel.columns]

# Rename _year
info_sel = info_sel.rename(columns={"_year": "year"})

# Merge
base = base.merge(info_sel, on=["stock_code", "year"], how="left")
print(f"  PROVINCE 非缺失: {base['province'].notna().mean():.1%}")
print(f"  IndustryCode 非缺失: {base['industry_code'].notna().mean():.1%}")


# ============================================================
# 4. 合并专利 (PT_LCDOMFORAPPLY) — Pivot by ApplyType
# ============================================================
print("\n" + "=" * 80)
print("4. 合并专利数据")
print("=" * 80)

pat["_year"] = std_year(pat["EndDate"])
pat["stock_code"] = std_code(pat["Symbol"])

# 只取国内专利 (Area == 1 或 "1" 或 "国内")
pat["_area_num"] = pd.to_numeric(pat["Area"], errors="coerce")
pat_domestic = pat[pat["_area_num"] == 1].copy()
print(f"  国内专利: {len(pat_domestic):,} / {len(pat):,}")

# 为每个 ApplyType 构造列
pat_pivot = pat_domestic.pivot_table(
    index=["stock_code", "_year"],
    columns="ApplyType",
    values=["Invention", "UtilityModel", "Design", "Patents"],
    aggfunc="sum"
).fillna(0)

# Flatten columns
pat_pivot.columns = [
    f"{var}_{atype}" for var, atype in pat_pivot.columns
]
pat_pivot = pat_pivot.reset_index()
pat_pivot = pat_pivot.rename(columns={"_year": "year"})

# 显式重命名专利列
TYPE_MAP = {
    "已申请": "apply",
    "已获得": "obtain",
    "已授权": "grant",
    "截至报告期末累计获得": "cum_obtain",
    "截止报告期末累计已被受理": "cum_accepted",
    "截止报告期末累计已授权": "cum_grant",
}
VAR_MAP = {
    "Invention": "invention",
    "UtilityModel": "utility",
    "Design": "design",
    "Patents": "patent",
}

pat_rename = {}
for c in pat_pivot.columns:
    if c in ["stock_code", "year"]:
        continue
    for v_cn, v_en in VAR_MAP.items():
        for t_cn, t_en in TYPE_MAP.items():
            if c == f"{v_cn}_{t_cn}":
                pat_rename[c] = f"{v_en}_{t_en}"
                break

pat_pivot = pat_pivot.rename(columns=pat_rename)
print(f"  专利 pivot: {len(pat_pivot):,} stock_code×year pairs")
print(f"  专利列: {[c for c in pat_pivot.columns if c not in ['stock_code','year']]}")

# Merge
base = base.merge(pat_pivot, on=["stock_code", "year"], how="left")

# 无专利记录 = 0 专利 (不是缺失)
pat_cols = [c for c in pat_pivot.columns if c not in ["stock_code", "year"]]
for c in pat_cols:
    if c in base.columns:
        base[c] = base[c].fillna(0)
print(f"  专利变量 fillna(0): {len(pat_cols)} 列")


# ============================================================
# 5. 合并研发投入 (PT_LCRDSPENDING)
# ============================================================
print("\n" + "=" * 80)
print("5. 合并研发投入")
print("=" * 80)

rd["_year"] = std_year(rd["EndDate"])
rd["stock_code"] = std_code(rd["Symbol"])

rd_cols = ["stock_code", "_year", "RDPerson", "RDPersonRatio",
           "RDSpendSum", "RDSpendSumRatio", "RDExpenses", "RDInvest"]
rd_sel = rd[rd_cols].copy()
rd_sel = rd_sel.rename(columns={"_year": "year"})

# Deduplicate
rd_sel = rd_sel.drop_duplicates(subset=["stock_code", "year"], keep="first")

for c in ["RDPerson", "RDPersonRatio", "RDSpendSum", "RDSpendSumRatio", "RDExpenses", "RDInvest"]:
    rd_sel[c] = pd.to_numeric(rd_sel[c], errors="coerce")

base = base.merge(rd_sel, on=["stock_code", "year"], how="left")
print(f"  RDSpendSum 非缺失: {base['RDSpendSum'].notna().mean():.1%}")


# ============================================================
# 6. 合并资产负债表 (FS_Combas)
# ============================================================
print("\n" + "=" * 80)
print("6. 合并资产负债表")
print("=" * 80)

bs["_year"] = std_year(bs["Accper"])
bs["stock_code"] = std_code(bs["Stkcd"])
bs_A = bs[bs["Typrep"] == "A"][["stock_code", "_year", "A001000000"]].copy()
bs_A = bs_A.rename(columns={"_year": "year", "A001000000": "total_assets"})
bs_A["total_assets"] = pd.to_numeric(bs_A["total_assets"], errors="coerce")
bs_A = bs_A.drop_duplicates(subset=["stock_code", "year"], keep="first")

base = base.merge(bs_A, on=["stock_code", "year"], how="left")
print(f"  total_assets 非缺失: {base['total_assets'].notna().mean():.1%}")


# ============================================================
# 7. 合并现金流量表 (FS_Comscfd)
# ============================================================
print("\n" + "=" * 80)
print("7. 合并现金流量表")
print("=" * 80)

cf["_year"] = std_year(cf["Accper"])
cf["stock_code"] = std_code(cf["Stkcd"])
cf_A = cf[cf["Typrep"] == "A"][["stock_code", "_year", "C001100000", "C001200000"]].copy()
cf_A = cf_A.rename(columns={
    "_year": "year",
    "C001100000": "cf_operating_inflow",      # 经营活动现金流入小计
    "C001200000": "cf_operating_outflow",     # 经营活动现金流出小计
})
for c in ["cf_operating_inflow", "cf_operating_outflow"]:
    cf_A[c] = pd.to_numeric(cf_A[c], errors="coerce")
cf_A = cf_A.drop_duplicates(subset=["stock_code", "year"], keep="first")

# 构造经营现金流净额
cf_A["cf_operating_net"] = cf_A["cf_operating_inflow"] - cf_A["cf_operating_outflow"]

base = base.merge(cf_A, on=["stock_code", "year"], how="left")
print(f"  cf_operating_net 非缺失: {base['cf_operating_net'].notna().mean():.1%}")


# ============================================================
# 8. 合并控制人 → 构造 SOE (HLD_Contrshr)
# ============================================================
print("\n" + "=" * 80)
print("8. 合并控制人 → 构造 SOE")
print("=" * 80)

ctr["_year"] = std_year(ctr["Reptdt"])
ctr["stock_code"] = std_code(ctr["Stkcd"])

# 取每个 firm-year 的第一条 (通常是主要控制人)
ctr_sel = ctr[["stock_code", "_year", "S0702b"]].copy()
ctr_sel = ctr_sel.drop_duplicates(subset=["stock_code", "_year"], keep="first")
ctr_sel = ctr_sel.rename(columns={"_year": "year", "S0702b": "controller_type"})

base = base.merge(ctr_sel, on=["stock_code", "year"], how="left")

# 构造 SOE:
# CSMAR 实际控制人性质编码规则 (企业关系人性质分类标准):
#   1xxx = 国有企业 (中央/地方)
#   2xxx = 民营企业/自然人
#   3xxx = 外资企业
#   其他 = 其他
base["soe"] = np.where(
    base["controller_type"].astype(str).str.startswith("1"), 1,
    np.where(base["controller_type"].astype(str).str.startswith("2"), 0, np.nan)
)
# soe=1: 国有企业; soe=0: 非国有(民营/外资/其他)
print(f"  controller_type 非缺失: {base['controller_type'].notna().mean():.1%}")
print(f"  SOE 构造完成:")
print(f"    soe=1 (国有): {(base['soe']==1).sum():,}")
print(f"    soe=0 (非国有): {(base['soe']==0).sum():,}")
print(f"    无法分类: {base['soe'].isna().sum():,}")
print(f"  controller_type 分布 (Top 10):")
for k, v in base["controller_type"].value_counts().head(10).items():
    print(f"    {k}: {v:,}")


# ============================================================
# 9. 合并政府补助 → 汇总 (FN_FN056)
# ============================================================
print("\n" + "=" * 80)
print("9. 汇总政府补助")
print("=" * 80)

sub["_year"] = std_year(sub["Accper"])
sub["stock_code"] = std_code(sub["Stkcd"])

# 只取合并报表 (Typrep = 1 or "1")
sub_mask = sub["Typrep"].astype(str).str.strip().isin(["1", "1.0"])
sub_A = sub[sub_mask].copy()
sub_A["Fn05602_num"] = pd.to_numeric(sub_A["Fn05602"], errors="coerce")
print(f"  政府补助合并报表: {len(sub_A):,} rows")

# 关键词规则: 研发相关补助
rd_keywords = [
    "研发", "科技", "创新", "高新", "专利", "技术", "R&D",
    "科研", "发明", "技改", "技术改造", "知识产权", "产业化",
    "新产品", "新工艺", "软件", "信息化", "数字化", "智能",
    "实验室", "工程中心", "技术中心", "研究院",
]
kw_pattern = "|".join(rd_keywords)

# 标记研发相关项目
sub_A["is_rd"] = sub_A["Fn05601"].astype(str).str.contains(kw_pattern, na=False)

# 按 firm-year 汇总
sub_total = sub_A.groupby(["stock_code", "_year"])["Fn05602_num"].sum().reset_index()
sub_total.columns = ["stock_code", "year", "total_subsidy"]

sub_rd = sub_A[sub_A["is_rd"]].groupby(["stock_code", "_year"])["Fn05602_num"].sum().reset_index()
sub_rd.columns = ["stock_code", "year", "rd_subsidy"]

# 也统计研发项目数量和匹配率
sub_rd_detail = sub_A.groupby(["stock_code", "_year"]).agg(
    total_subsidy_items=("Fn05602_num", "count"),
    rd_subsidy_items=("is_rd", "sum"),
).reset_index()
sub_rd_detail.columns = ["stock_code", "year", "total_subsidy_items", "rd_subsidy_items"]

# Merge
base = base.merge(sub_total, on=["stock_code", "year"], how="left")
base = base.merge(sub_rd, on=["stock_code", "year"], how="left")
base = base.merge(sub_rd_detail, on=["stock_code", "year"], how="left")

rd_match_pct = sub_A["is_rd"].mean()
print(f"  研发关键词匹配率: {rd_match_pct:.1%}")
print(f"  有政府补助的企业-年: {base['total_subsidy'].notna().sum():,}")
print(f"  有研发补助的企业-年: {base['rd_subsidy'].notna().sum():,}")


# ============================================================
# 10. 构造政策变量
# ============================================================
print("\n" + "=" * 80)
print("10. 构造政策变量")
print("=" * 80)

# manufacturing: industry_code 以 "C" 开头 (制造业)
# 如果 industry_code 缺失，尝试从 industry_name 判断
base["manufacturing"] = 0
code_mask = base["industry_code"].notna()
base.loc[code_mask, "manufacturing"] = (
    base.loc[code_mask, "industry_code"].astype(str).str.startswith("C")
).astype(int)

# 补充: industry_name 包含"制造"
name_mask = base["manufacturing"] == 0
base.loc[name_mask, "manufacturing"] = (
    base.loc[name_mask, "industry_name"].astype(str).str.contains("制造", na=False)
).astype(int)

print(f"  制造业企业: {base['manufacturing'].mean():.1%}")

# Post indicators
base["post2020"] = (base["year"] >= 2020).astype(int)
base["post2021"] = (base["year"] >= 2021).astype(int)
base["post2022"] = (base["year"] >= 2022).astype(int)
base["post2023"] = (base["year"] >= 2023).astype(int)

# DID interactions
base["manufacturing_post2021"] = base["manufacturing"] * base["post2021"]
base["manufacturing_post2022"] = base["manufacturing"] * base["post2022"]
base["manufacturing_post2020"] = base["manufacturing"] * base["post2020"]  # placebo

# R&D deduction rate by year × industry
# 政策历程:
#   2016-2017: 全行业 50%
#   2018-2020: 全行业 75% (财税[2018]99号)
#   2021-2022: 制造业 100% (财税[2021]13号), 非制造业 75%
#   2023+:     全行业 100% (财税[2022]28号)
base["rd_deduction_rate"] = 0.5                                        # 2016-2017 default
base.loc[(base["year"] >= 2018) & (base["year"] <= 2020), "rd_deduction_rate"] = 0.75
base.loc[(base["year"] >= 2021) & (base["year"] <= 2022) & (base["manufacturing"] == 1), "rd_deduction_rate"] = 1.0
base.loc[(base["year"] >= 2021) & (base["year"] <= 2022) & (base["manufacturing"] == 0), "rd_deduction_rate"] = 0.75
base.loc[base["year"] >= 2023, "rd_deduction_rate"] = 1.0

print(f"  rd_deduction_rate 分布:")
for yr in sorted(base["year"].dropna().unique()):
    mfg_val = base[(base["manufacturing"]==1) & (base["year"]==yr)]["rd_deduction_rate"].iloc[0] if ((base["manufacturing"]==1) & (base["year"]==yr)).any() else "N/A"
    non_val = base[(base["manufacturing"]==0) & (base["year"]==yr)]["rd_deduction_rate"].iloc[0] if ((base["manufacturing"]==0) & (base["year"]==yr)).any() else "N/A"
    print(f"    {int(yr)}: 制造业={mfg_val}, 非制造业={non_val}")

# tax_saving_est: estimated tax saving from R&D super-deduction
# = RDSpendSum × rd_deduction_rate × statutory_tax_rate(0.25)
# Note: 这是估算值，不是真实退税数据
base["rd_expense"] = base["RDSpendSum"]  # 更名，明确这是真实研发投入

# 研发强度 (自行计算 + 原始口径)
base["rd_intensity_calc"] = np.where(
    (base["RDSpendSum"].notna()) & (base["revenue"].notna()) & (base["revenue"] > 0),
    base["RDSpendSum"] / base["revenue"] * 100,
    np.nan
)

# tax_saving_est
base["tax_saving_est"] = np.where(
    base["RDSpendSum"].notna() & (base["RDSpendSum"] > 0),
    base["RDSpendSum"] * base["rd_deduction_rate"] * 0.25,
    0
)

# rd_tax_deduction_est: estimated super-deduction amount
base["rd_tax_deduction_est"] = np.where(
    base["RDSpendSum"].notna() & (base["RDSpendSum"] > 0),
    base["RDSpendSum"] * base["rd_deduction_rate"],
    0
)

print(f"  tax_saving_est > 0: {(base['tax_saving_est'] > 0).sum():,}")


# ============================================================
# 11. 构造对数变换变量
# ============================================================
print("\n" + "=" * 80)
print("11. 构造对数变换变量")
print("=" * 80)

# Patent outcome variables (log1p)
for col in ["invention_已申请", "invention_已授权", "patent_已申请", "patent_已授权",
            "invention_cum_获得", "invention_cum_已被受理", "invention_cum_已授权"]:
    if col in base.columns:
        base[f"ln_{col}"] = np.log1p(pd.to_numeric(base[col], errors="coerce").clip(lower=0))

# Financial variables
base["ln_assets"] = np.log1p(pd.to_numeric(base["total_assets"], errors="coerce").clip(lower=0))

# R&D & tax
for col in ["rd_expense", "tax_saving_est", "rd_tax_deduction_est", "rd_subsidy", "total_subsidy"]:
    if col in base.columns:
        base[f"ln_{col}"] = np.log1p(pd.to_numeric(base[col], errors="coerce").clip(lower=0))

# ROA, leverage
if "revenue" in base.columns and "total_assets" in base.columns:
    base["roa"] = np.where(
        base["profit_before_tax"].notna() & base["total_assets"].notna() & (base["total_assets"] > 0),
        base["profit_before_tax"] / base["total_assets"],
        np.nan
    )

# Leverage (use total_liability if available, but we don't have it directly)
# We have total_assets only from FS_Combas; no total_liability
# Use the existing formula pattern: lev = total_liability / total_assets
# For now, lev is unavailable from direct data. Skip or construct alternative.
# We'll note this in the report.

# Firm age
if "establish_date" in base.columns:
    base["_est_year"] = pd.to_datetime(base["establish_date"], errors="coerce", format="mixed").dt.year
    base["firm_age"] = base["year"] - base["_est_year"]
    base["firm_age"] = base["firm_age"].clip(lower=0)


# ============================================================
# 12. Winsorize
# ============================================================
print("\n" + "=" * 80)
print("12. Winsorize 连续变量 (1%, 99%)")
print("=" * 80)

winsor_cols = []
for c in base.columns:
    if base[c].dtype in ['float64', 'int64']:
        if base[c].notna().sum() > 100:
            winsor_cols.append(c)

for c in winsor_cols:
    v = base[c].dropna()
    if len(v) > 0:
        lo, hi = v.quantile(0.01), v.quantile(0.99)
        if lo < hi:
            base[c] = base[c].clip(lo, hi)
print(f"  Winsorized {len(winsor_cols)} variables")


# ============================================================
# 13. 生成最终面板
# ============================================================
print("\n" + "=" * 80)
print("13. 生成最终面板")
print("=" * 80)

# 排序
base = base.sort_values(["stock_code", "year"]).reset_index(drop=True)

# 按样本切分标记
base["sample_all"] = base["year"].between(2016, 2024)
base["sample_2017_2022"] = base["year"].between(2017, 2022)
base["sample_2017_2024"] = base["year"].between(2017, 2024)
base["sample_2019_2024"] = base["year"].between(2019, 2024)
base["sample_2017_2024_no2023_2024"] = base["year"].between(2017, 2022)  # same as 2017-2022
base["sample_2016_2022"] = base["year"].between(2016, 2022)

# 保存
out_cols = [c for c in base.columns if not c.startswith("_")]
base_out = base[out_cols].copy()

# 保存前重命名关键列 (简化列名)
simple_rename = {}
for c in base_out.columns:
    new = c
    for cn, en in [("已申请", "apply"), ("已授权", "grant"), ("已获得", "obtain"),
                    ("截至报告期末累计", "cum_"), ("截止报告期末累计", "cum_"),
                    ("已被受理", "accepted")]:
        new = new.replace(cn, en)
    simple_rename[c] = new

base_save = base_out.rename(columns=simple_rename)

csv_path = OUT_DIR / "firm_panel_v2.csv"
xlsx_path = OUT_DIR / "firm_panel_v2.xlsx"
base_save.to_csv(csv_path, index=False, encoding="utf-8-sig")
base_save.to_excel(xlsx_path, index=False)

print(f"\n  已保存: {csv_path} ({len(base_save):,} rows × {len(base_save.columns)} cols)")
print(f"  已保存: {xlsx_path}")

# 样本摘要
for sample_name, sample_col in [
    ("2016-2024", "sample_all"),
    ("2017-2022 (基准)", "sample_2017_2022"),
    ("2017-2024", "sample_2017_2024"),
    ("2016-2022", "sample_2016_2022"),
]:
    s = base[sample_col]
    n = s.sum()
    firms = base.loc[s, "stock_code"].nunique()
    print(f"  {sample_name}: {n:,} obs × {firms:,} firms")

# 覆盖率报告
print(f"\n  关键变量覆盖率:")
key_vars = [
    "revenue", "profit_before_tax", "income_tax_expense", "etr",
    "total_assets", "ln_assets",
    "province", "industry_code", "manufacturing",
    "RDSpendSum", "rd_intensity_calc", "RDPerson",
    "invention_apply", "invention_grant", "patent_apply", "patent_grant",
    "soe", "total_subsidy", "rd_subsidy",
    "cf_operating_net",
    "tax_saving_est", "rd_tax_deduction_est",
]
for v in key_vars:
    if v in base.columns:
        pct = base[v].notna().mean()
        print(f"    {v:30s}: {pct:.1%}")
    else:
        # check for alternative names
        alt = [c for c in base.columns if v in c]
        if alt:
            pct = base[alt[0]].notna().mean()
            print(f"    {alt[0]:30s}: {pct:.1%}")
        else:
            print(f"    {v:30s}: NOT FOUND")

print("\n" + "=" * 80)
print("DONE: firm_panel_v2 构建完成")
print("=" * 80)
