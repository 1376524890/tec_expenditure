"""
自动化采集省级R&D经费支出数据
来源: 国家统计局 中国统计年鉴 / 中国科技统计年鉴
采集年份: 2017-2023 (2011-2016已覆盖但缺R&D支出, 2024已有)
"""
import asyncio
import pandas as pd
import numpy as np
from pathlib import Path
from playwright.async_api import async_playwright
import re
import time

# 各省名称映射 (用于后续匹配)
PROVINCE_NAMES = [
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省",
    "上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省",
    "重庆市", "四川省", "贵州省", "云南省", "西藏自治区",
    "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区"
]

async def fetch_rd_expenditure_from_stats_gov(year: int):
    """从国家统计局年鉴获取省级R&D经费支出"""
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # 中国统计年鉴 - 科学技术章节
            # 表20-1: 研究与试验发展(R&D)经费内部支出
            url = f"https://www.stats.gov.cn/sj/ndsj/{year}/indexch.htm"
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(2000)

            # 获取页面HTML,查找R&D相关链接
            content = await page.content()

            # 查找第20章 科学技术
            # 匹配表20-x的链接
            rd_links = []
            links = await page.query_selector_all('a')
            for link in links:
                text = await link.text_content()
                href = await link.get_attribute('href')
                if text and href:
                    if 'R&D' in text or '研究与试验发展' in text or '科技' in text:
                        rd_links.append((text.strip(), href))

            print(f"Year {year}: Found {len(rd_links)} R&D-related links")
            for text, href in rd_links[:10]:
                print(f"  {text}: {href}")

        except Exception as e:
            print(f"Error fetching year {year}: {e}")
        finally:
            await browser.close()

    return results

async def fetch_from_tjnj_site():
    """从统计年鉴镜像站获取数据"""
    # 使用 tjnj.net 或 zgtjnj.org
    pass

async def main():
    print("=== 开始采集省级R&D经费支出数据 ===\n")

    # 先测试2023年年鉴
    await fetch_rd_expenditure_from_stats_gov(2023)

if __name__ == "__main__":
    asyncio.run(main())
