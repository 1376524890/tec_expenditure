"""
将从公开统计公报中采集的2017-2023年省级R&D经费数据
编译为结构化CSV并合并到省级面板数据集
"""
import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================
# 从《全国科技经费投入统计公报》采集的省级R&D经费内部支出
# 数据来源: 国家统计局、科技部、财政部联合发布
# 单位: 亿元
# ============================================================

# 省份全称映射 (公报使用简称 -> 全称)
NAME_MAP = {
    "北京": "北京市", "天津": "天津市", "河北": "河北省", "山西": "山西省",
    "内蒙古": "内蒙古自治区", "辽宁": "辽宁省", "吉林": "吉林省", "黑龙江": "黑龙江省",
    "上海": "上海市", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "广西": "广西壮族自治区",
    "海南": "海南省", "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
    "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省", "甘肃": "甘肃省",
    "青海": "青海省", "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
}

# 各省R&D经费内部支出 (亿元) - 完整数据
# 年份: 2017, 2018, 2019, 2020, 2021, 2022, 2023
rd_data = {
    "北京": [1579.7, 1870.8, 2233.6, 2326.6, 2629.3, 2843.3, 2947.1],
    "天津": [458.7, 492.4, 463.0, 485.0, 574.3, 568.7, None],
    "河北": [452.0, 499.7, 566.7, 634.4, 745.5, 848.9, None],
    "山西": [148.2, 175.8, 191.2, 211.1, 251.9, 273.7, None],
    "内蒙古": [132.3, 129.2, 147.8, 161.1, 190.1, 209.5, None],
    "辽宁": [429.9, 460.1, 508.5, 549.0, 600.4, 620.9, None],
    "吉林": [128.0, 115.0, 148.4, 159.5, 183.7, 187.3, None],
    "黑龙江": [146.6, 135.0, 146.6, 173.2, 194.6, 217.8, None],
    "上海": [1205.2, 1359.2, 1524.6, 1615.7, 1819.8, 1981.6, 2049.6],
    "江苏": [2260.1, 2504.4, 2779.5, 3005.9, 3438.6, 3835.4, 4212.3],
    "浙江": [1266.3, 1445.7, 1669.8, 1859.9, 2157.7, 2416.8, 2640.2],
    "安徽": [564.9, 649.0, 754.0, 883.2, 1006.1, 1152.5, 1264.7],
    "福建": [543.1, 642.8, 753.7, 842.4, 968.7, 1082.1, 1171.7],
    "江西": [255.8, 310.7, 384.3, 430.7, 502.2, 558.2, None],
    "山东": [1753.0, 1643.3, 1494.7, 1681.9, 1944.7, 2180.4, 2386.0],
    "河南": [582.1, 671.5, 793.0, 901.3, 1018.8, 1143.3, 1211.7],
    "湖北": [700.6, 822.1, 957.9, 1005.3, 1160.2, 1254.7, 1408.2],
    "湖南": [568.5, 658.3, 787.2, 898.7, 1028.9, 1175.3, 1283.9],
    "广东": [2345.6, 2704.7, 3098.5, 3479.9, 4002.2, 4411.9, 4802.6],
    "广西": [142.2, 144.9, 167.1, 173.2, 199.5, 217.9, None],
    "海南": [23.1, 26.9, 29.9, 36.6, 47.0, 68.4, None],
    "重庆": [364.6, 410.2, 469.6, 526.8, 603.8, 686.6, None],
    "四川": [637.8, 737.1, 871.0, 1055.3, 1214.5, 1215.0, 1357.8],
    "贵州": [95.9, 121.6, 144.7, 161.7, 180.4, 199.3, None],
    "云南": [157.8, 187.3, 220.0, 246.0, 281.9, 313.5, None],
    "西藏": [2.9, 3.7, 4.3, 4.4, 6.0, 7.0, None],
    "陕西": [460.9, 532.4, 584.6, 632.3, 700.6, 769.6, None],
    "甘肃": [88.4, 97.1, 110.2, 109.6, 129.5, 144.1, None],
    "青海": [17.9, 17.3, 20.6, 21.3, 26.8, 28.8, None],
    "宁夏": [38.9, 45.6, 54.5, 59.6, 70.4, 79.4, None],
    "新疆": [57.0, 64.3, 64.1, 61.6, 78.3, 91.0, None],
}

YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023]

def main():
    # 构建DataFrame
    rows = []
    for short_name, values in rd_data.items():
        full_name = NAME_MAP.get(short_name, short_name)
        for i, year in enumerate(YEARS):
            if values[i] is not None:
                rows.append({
                    "province": full_name,
                    "year": year,
                    "province_rd_exp": values[i],
                })

    new_df = pd.DataFrame(rows)
    print(f"新采集数据: {len(new_df)} 行")
    print(f"省份数: {new_df['province'].nunique()}")
    print(f"年份范围: {new_df['year'].min()}-{new_df['year'].max()}")
    print(f"缺失: {new_df['province_rd_exp'].isna().sum()}")

    # 计算R&D投入强度 (province_rd_intensity = province_rd_exp / province_gdp * 100)
    # 需要从现有面板获取GDP

    # 读取现有省级面板
    existing = pd.read_csv("D:/科技创新支出/data/provincial_panel_full.csv")
    print(f"\n现有数据: {len(existing)} 行, province_rd_exp覆盖率: {existing['province_rd_exp'].notna().mean():.2%}")

    # 合并: 用新采集的province_rd_exp补充
    # 保留现有数据中已有的province_rd_exp (如果有), 用新数据填充缺失
    merged = existing.copy()

    # 将新数据merge进去
    merged = merged.merge(
        new_df,
        on=["province", "year"],
        how="left",
        suffixes=("_old", "_new")
    )

    # 优先使用旧数据(如有), 否则用新数据
    if "province_rd_exp_old" in merged.columns:
        merged["province_rd_exp"] = merged["province_rd_exp_old"].fillna(merged["province_rd_exp_new"])
        merged = merged.drop(columns=["province_rd_exp_old", "province_rd_exp_new"])
    else:
        merged["province_rd_exp"] = merged["province_rd_exp_new"]
        merged = merged.drop(columns=["province_rd_exp_new"])

    # 重新计算R&D投入强度
    # province_rd_intensity = province_rd_exp / gdp * 100
    merged["province_rd_intensity"] = np.where(
        merged["province_rd_exp"].notna() & merged["gdp"].notna() & (merged["gdp"] > 0),
        merged["province_rd_exp"] / merged["gdp"] * 100,
        np.nan
    )

    # 同时确保2011-2016年也有province_rd_exp (从search也补上)
    # 但这次只采集了2017-2023, 更早年份仍需从其他来源补充

    print(f"\n合并后province_rd_exp覆盖率: {merged['province_rd_exp'].notna().mean():.2%}")
    print(f"合并后province_rd_intensity覆盖率: {merged['province_rd_intensity'].notna().mean():.2%}")

    # 年度覆盖情况
    print("\n逐年province_rd_exp覆盖:")
    print(merged.groupby("year")["province_rd_exp"].apply(lambda x: x.notna().sum()))

    # 保存
    output_path = "D:/科技创新支出/data/provincial_panel_full.csv"
    merged.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n已保存更新后的省级面板: {output_path}")

    # 也保存一份单独的R&D数据
    new_df.to_csv("D:/科技创新支出/data/province_rd_exp_collected.csv", index=False, encoding="utf-8-sig")
    print(f"已保存R&D采集数据: D:/科技创新支出/data/province_rd_exp_collected.csv")

    # 报告采集情况
    print("\n=== 数据采集报告 ===")
    print(f"来源: 国家统计局 全国科技经费投入统计公报 (2018-2024年发布)")
    print(f"覆盖年份: 2017-2023 (7年)")
    print(f"覆盖省份: 31个")
    total_cells = 31 * 7
    collected = new_df['province_rd_exp'].notna().sum()
    print(f"数据完整度: {collected}/{total_cells} ({collected/total_cells:.1%})")
    print(f"未采集省份-年份 (公报中未单独列出完整数据):")
    for short_name, values in rd_data.items():
        missing_years = [YEARS[i] for i, v in enumerate(values) if v is None]
        if missing_years:
            print(f"  {short_name}: {missing_years}")


if __name__ == "__main__":
    main()
