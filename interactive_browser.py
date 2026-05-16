"""
交互式浏览器 — 访问中国统计年鉴获取科学技术/R&D数据
www.stats.gov.cn 可达
"""
import asyncio
from playwright.async_api import async_playwright

async def show_page_info(page):
    """显示当前页面信息"""
    title = await page.title()
    url = page.url
    print(f"\n{'='*60}")
    print(f"当前页面: {title}")
    print(f"URL: {url}")
    print(f"{'='*60}")

async def show_links(page, keyword=None):
    """显示页面上的链接"""
    links = await page.query_selector_all('a')
    found = []
    for link in links:
        text = (await link.text_content()).strip()
        href = await link.get_attribute('href')
        if text and href:
            if keyword is None or keyword in text:
                found.append((text[:80], href[:120]))
    for text, href in found[:30]:
        print(f"  [{text}] -> {href}")
    print(f"  (共 {len(found)} 条)")
    return found

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1400, "height": 900})

        # 访问统计年鉴首页
        url = "https://www.stats.gov.cn/sj/ndsj/"
        print(f"正在打开: {url}")
        await page.goto(url, timeout=30000)
        await page.wait_for_timeout(2000)

        await show_page_info(page)
        await page.screenshot(path="D:/科技创新支出/screenshots/interactive_01.png")
        print("截图: screenshots/interactive_01.png")

        # 显示年鉴年份链接
        print("\n年鉴年份:")
        await show_links(page, "202")

        print("\n" + "="*60)
        print("浏览器已打开，将保持 300 秒")
        print("发送操作指令来控制浏览器")
        print("="*60)

        await asyncio.sleep(300)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
