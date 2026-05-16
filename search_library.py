"""
使用本地 Chrome 自动搜索图书馆数据库
- 先启动 Chrome 调试端口，再通过 CDP 连接
"""
import asyncio
import subprocess
import time
import os
from pathlib import Path
from browser_use import BrowserSession


LIBRARY_URL = "https://lib-443.webvpn.cufe.edu.cn/"

DATABASES = {
    "CSMAR": "https://www.gtarsc.com/",
    "CNRDS": "https://www.cnrds.com/",
    "CNIPA_专利检索": "https://pss-system.cponline.cnipa.gov.cn/",
    "国家统计局": "https://data.stats.gov.cn/",
    "中国政府采购网": "https://pub.ccgp.gov.cn/",
    "国家税务总局政策库": "https://fgk.chinatax.gov.cn/",
}

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA = r"C:\Users\MarkTom\AppData\Local\Google\Chrome\User Data"
DEBUG_PORT = 9222


async def js_eval(session: BrowserSession, expression: str):
    try:
        result = await session.cdp_client.send.Runtime.evaluate(params={
            'expression': expression,
            'returnByValue': True,
        })
        return result.get('result', {}).get('value', None)
    except Exception as e:
        return f"JS_ERROR: {e}"


async def find_links(session: BrowserSession, keywords: list[str]) -> list[dict]:
    import json as _json
    kw_json = _json.dumps(keywords)
    script = f"""
        (() => {{
            const links = document.querySelectorAll('a');
            const keywords = {kw_json};
            const found = [];
            links.forEach(link => {{
                const text = (link.textContent || '').trim();
                const href = link.href || '';
                for (const kw of keywords) {{
                    if (text.includes(kw) || href.toLowerCase().includes(kw.toLowerCase())) {{
                        found.push({{text: text.substring(0, 150), href: href}});
                        break;
                    }}
                }}
            }});
            return found.slice(0, 40);
        }})()
    """
    return await js_eval(session, script) or []


def start_chrome():
    """启动带调试端口的 Chrome"""
    print("启动 Chrome (远程调试模式)...")

    # Kill any existing Chrome
    os.system("taskkill /F /IM chrome.exe 2>nul >nul")
    time.sleep(2)

    proc = subprocess.Popen(
        [
            CHROME_PATH,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={USER_DATA}",
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            LIBRARY_URL,  # 直接打开图书馆
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    print(f"  Chrome PID: {proc.pid}")
    return proc


async def main():
    chrome_proc = start_chrome()

    cdp_url = f"http://127.0.0.1:{DEBUG_PORT}/"
    session = BrowserSession(cdp_url=cdp_url)

    try:
        await session.start()

        # ====== Step 1: 当前页面状态 ======
        print("=" * 60)
        print("Step 1: 检查当前页面")
        print("=" * 60)
        await asyncio.sleep(2)
        title = await session.get_current_page_title()
        url = await js_eval(session, 'window.location.href')
        print(f"标题: {title}")
        print(f"URL: {url}")
        await session.take_screenshot(path="screenshots/01_library_home.png", full_page=True)
        print("截图: screenshots/01_library_home.png")

        # ====== Step 2: 查找数据库入口 ======
        print("\n" + "=" * 60)
        print("Step 2: 查找数据库导航入口")
        print("=" * 60)

        entry_kw = ['数据库', '电子资源', '中文资源', '试用', '数字资源', '期刊']
        portal = await find_links(session, entry_kw)
        print(f"找到 {len(portal)} 个入口:")
        for link in portal[:20]:
            print(f"  [{link['text'][:80]}]")
            print(f"  => {link['href'][:120]}")
            print()

        # ====== Step 3: 页面文本 ======
        print("=" * 60)
        print("Step 3: 页面主要内容")
        print("=" * 60)
        text = await js_eval(session, 'document.body?.innerText?.substring(0, 2500) || ""')
        print(text)

        # ====== Step 4: 搜索数据源 ======
        print("\n" + "=" * 60)
        print("Step 4: 搜索数据源关键词")
        print("=" * 60)

        db_kw = [
            'CSMAR', 'CNRDS', 'Wind', '国泰安', '万得', '专利',
            '统计年鉴', '政府采购', 'CNIPA', '国家统计局', '同花顺',
            'iFinD', '马克', 'IncoPat', '智慧芽',
            '创新专利', '高技术', '科技经费', 'WIPO',
        ]
        db_links = await find_links(session, db_kw)
        print(f"找到 {len(db_links)} 个数据源链接:")
        for link in db_links:
            print(f"  [{link['text'][:80]}]")
            print(f"  => {link['href'][:120]}")
            print()

        # ====== Step 5: 逐个检查数据库 ======
        print("=" * 60)
        print("Step 5: 逐个检查外部数据库")
        print("=" * 60)

        for name, db_url in DATABASES.items():
            print(f"\n--- {name} ---")
            try:
                await session.navigate_to(db_url)
                await asyncio.sleep(3)
                pt = await session.get_current_page_title()
                pu = await js_eval(session, 'window.location.href')
                print(f"  标题: {pt}")
                print(f"  URL: {pu[:120]}")
                safe = name.replace(" ", "_").replace("/", "_")
                await session.take_screenshot(path=f"screenshots/db_{safe}.png")
            except Exception as e:
                print(f"  失败: {e}")

        print("\n✓ 完成！截图保存在 screenshots/")
        print("Chrome 保持打开，手动操作后可直接关闭窗口。")

    finally:
        await session.stop()
        # 不关 Chrome，让用户手动操作
        print("CDP 会话已断开，Chrome 保持运行。")


if __name__ == "__main__":
    Path("screenshots").mkdir(exist_ok=True)
    asyncio.run(main())
