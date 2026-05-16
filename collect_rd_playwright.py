"""
使用 Playwright 直接采集省级R&D经费支出数据
来源: 国家统计局数据浏览器 / 统计年鉴
"""
import asyncio
import pandas as pd
import numpy as np
from pathlib import Path
from playwright.async_api import async_playwright
import re
import json
import time

OUTPUT_DIR = Path("D:/科技创新支出/data")

PROVINCE_MAP = {
    "北京": "北京市", "天津": "天津市", "河北": "河北省", "山西": "山西省",
    "内蒙古": "内蒙古自治区", "辽宁": "辽宁省", "吉林": "吉林省", "黑龙江": "黑龙江省",
    "上海": "上海市", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "广西": "广西壮族自治区",
    "海南": "海南省", "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
    "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省", "甘肃": "甘肃省",
    "青海": "青海省", "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
}

async def try_easyquery_api(page):
    """尝试通过NBS easyquery API获取数据"""
    print("=== 尝试 easyquery API ===")

    # 首先获取指标树，找到R&D经费支出的代码
    tree_url = "https://data.stats.gov.cn/easyquery/api?m=QueryTree&id=zb"
    try:
        response = await page.request.get(tree_url)
        if response.ok:
            data = await response.json()
            print(f"指标树获取成功，顶层节点: {len(data) if isinstance(data, list) else 'not list'}")

            # 搜索R&D相关指标
            def search_tree(nodes, keyword, path=""):
                results = []
                if not isinstance(nodes, list):
                    return results
                for node in nodes:
                    if isinstance(node, dict):
                        name = node.get("name", "")
                        code = node.get("id", "")
                        if keyword in name:
                            results.append((code, name, path))
                        if "children" in node:
                            results.extend(search_tree(node["children"], keyword, f"{path}/{name}"))
                return results

            rd_indicators = search_tree(data, "R&D") + search_tree(data, "研发") + search_tree(data, "试验发展")
            print(f"找到 {len(rd_indicators)} 个R&D相关指标:")
            for code, name, path in rd_indicators[:20]:
                print(f"  {code}: {name} (路径: {path})")
            return rd_indicators
    except Exception as e:
        print(f"指标树获取失败: {e}")
    return []


async def try_data_browser(page):
    """通过国家统计局数据浏览器页面获取数据"""
    print("\n=== 尝试数据浏览器页面 ===")

    # 访问分省年度数据页面
    url = "https://data.stats.gov.cn/easyquery.htm?cn=E0103"
    await page.goto(url, timeout=60000)
    await page.wait_for_timeout(5000)

    # 截图看看页面状态
    await page.screenshot(path=str(OUTPUT_DIR / "nbs_page_screenshot.png"))
    print(f"页面截图已保存")

    # 尝试获取页面内容
    content = await page.content()

    # 查找R&D相关的可点击元素
    # 常见的指标代码模式
    rd_patterns = [
        "研究与试验发展",
        "R&D经费",
        "研发经费",
        "试验发展经费",
    ]

    for pattern in rd_patterns:
        elements = await page.query_selector_all(f'text="{pattern}"')
        if elements:
            print(f"找到包含'{pattern}'的元素: {len(elements)}个")

    # 尝试使用搜索功能
    try:
        search_input = await page.query_selector('input[type="text"]')
        if search_input:
            await search_input.fill("研究与试验发展经费内部支出")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(3000)
            print("已输入搜索关键词")
    except Exception as e:
        print(f"搜索框操作失败: {e}")

    return content


async def try_yearbook_tables(page):
    """尝试从统计年鉴HTML表格中直接提取数据"""
    print("\n=== 尝试年鉴表格直接提取 ===")

    all_data = {}

    # 各年年鉴URL
    yearbooks = {
        2022: "https://www.stats.gov.cn/sj/ndsj/2023/indexch.htm",  # 2023年鉴=2022数据
        2021: "https://www.stats.gov.cn/sj/ndsj/2022/indexch.htm",
        2020: "https://www.stats.gov.cn/sj/ndsj/2021/indexch.htm",
        2019: "https://www.stats.gov.cn/sj/ndsj/2020/indexch.htm",
        2018: "https://www.stats.gov.cn/sj/ndsj/2019/indexch.htm",
        2017: "https://www.stats.gov.cn/sj/ndsj/2018/indexch.htm",
    }

    for data_year, url in yearbooks.items():
        print(f"\n尝试获取 {data_year}年 数据...")
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(3000)

            # 年鉴页面使用frameset,需要切换到右侧frame
            frames = page.frames
            print(f"  页面有 {len(frames)} 个 frame")

            for i, frame in enumerate(frames):
                frame_url = frame.url
                frame_name = frame.name
                print(f"  Frame {i}: name={frame_name}, url={frame_url[:100]}")

                # 尝试在右侧frame中找"科技"或"R&D"链接
                if "indexch" not in frame_url and "left" not in frame_name.lower():
                    try:
                        links = await frame.query_selector_all('a')
                        for link in links:
                            text = await link.text_content()
                            if text and any(kw in text for kw in ['科技', 'R&D', '研究', 'Science']):
                                href = await link.get_attribute('href')
                                print(f"    找到链接: {text.strip()} -> {href}")
                    except Exception as e:
                        pass

        except Exception as e:
            print(f"  获取 {data_year} 失败: {e}")

    return all_data


async def try_alternative_sources(page):
    """尝试从其他公开数据源获取"""
    print("\n=== 尝试替代数据源 ===")

    # 方案: 全国科技经费投入统计公报 (每年发布，包含分省R&D数据)
    # 2022年公报: https://www.stats.gov.cn/sj/zxfb/202309/t20230918_1942928.html
    gazette_urls = [
        ("2023年公报(2024发布)", "https://www.stats.gov.cn/sj/zxfb/202410/t20241008_1956614.html"),
        ("2022年公报(2023发布)", "https://www.stats.gov.cn/sj/zxfb/202309/t20230918_1942928.html"),
    ]

    for name, url in gazette_urls:
        try:
            print(f"\n尝试: {name}")
            response = await page.request.get(url)
            if response.ok:
                text = await response.text()
                # 查找R&D经费相关数字
                # 公报中通常以文字段落形式呈现各省数据
                print(f"  页面长度: {len(text)} 字符")
                # 提取包含"亿元"和省份的句子
                sentences = re.findall(r'[^。]*?(?:北京|天津|河北|山西|内蒙古|辽宁|吉林|黑龙江|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆)[^。]*?R&D[^。]*?亿元[^。]*?。', text)
                if not sentences:
                    sentences = re.findall(r'[^。]*?R&D[^。]*?(?:北京|天津|河北)[^。]*?亿元[^。]*?。', text)
                print(f"  找到 {len(sentences)} 个相关句子")
                for s in sentences[:5]:
                    print(f"    {s[:200]}")
        except Exception as e:
            print(f"  失败: {e}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 方案1: 尝试API
        indicators = await try_easyquery_api(page)

        # 方案2: 尝试数据浏览器
        # content = await try_data_browser(page)

        # 方案3: 尝试年鉴表格
        # yearbook_data = await try_yearbook_tables(page)

        # 方案4: 尝试替代来源
        await try_alternative_sources(page)

        await browser.close()

    print("\n=== 采集完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
