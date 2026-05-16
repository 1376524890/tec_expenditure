"""
本地 Browser Agent 模板 — 学术数据库自动化数据采集
=====================================================
适用场景: 通过图书馆 VPN 访问 CSMAR/Wind/CNRDS/国家统计局 等学术数据库
核心依赖: playwright, pandas, openpyxl
前置条件: Chrome 已启动带 --remote-debugging-port=9222
"""

import asyncio, sys, io, json, re, urllib.parse
from pathlib import Path
from playwright.async_api import async_playwright

# ============================================================
# 0. 基础设施
# ============================================================

# Windows 中文输出兼容
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

Path("screenshots").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)


class BrowserAgent:
    """封装 Playwright CDP 连接的轻量 Agent"""

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222/"):
        self.cdp_url = cdp_url
        self.browser = None
        self.page = None

    async def connect(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
        self.page = self.browser.contexts[0].pages[0]
        return self

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # --- 导航 ---
    async def goto(self, url: str, wait: float = 3.0):
        """导航并等待 SPA 渲染"""
        await self.page.goto(url, timeout=20000)
        await asyncio.sleep(wait)

    # --- 信息提取 ---
    async def text(self, max_chars: int = 5000) -> str:
        """获取页面纯文本"""
        raw = await self.page.evaluate(
            f'document.body?.innerText?.substring(0, {max_chars}) || ""'
        )
        return ''.join(c if c.isprintable() or c in '\n\r\t' else ' ' for c in raw)

    async def title(self) -> str:
        return await self.page.evaluate('document.title')

    async def url(self) -> str:
        return await self.page.evaluate('window.location.href')

    async def screenshot(self, name: str):
        await self.page.screenshot(path=f"screenshots/{name}.png", full_page=True)

    # --- 链接搜索 ---
    async def find_links(self, keywords: list[str], limit: int = 40) -> list[dict]:
        """搜索包含关键词的链接"""
        kw_json = json.dumps(keywords)
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
                return found.slice(0, {limit});
            }})()
        """
        return await self.page.evaluate(script) or []

    # --- JS 操作 ---
    async def js_click(self, text: str) -> bool:
        """通过文本内容点击元素（绕过 visibility check）"""
        result = await self.page.evaluate("""
            (searchText) => {
                const all = document.querySelectorAll('span, a, button, div');
                for (const el of all) {
                    if (el.childNodes.length === 1 &&
                        el.childNodes[0].nodeType === 3 &&
                        el.textContent.trim() === searchText) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }
        """, text)
        return result

    async def fetch_api(self, endpoint: str) -> str:
        """在浏览器上下文内调用同源 API（绕过 WAF）"""
        return await self.page.evaluate("""
            (url) => fetch(url, {credentials: 'include'})
                .then(r => r.text())
        """, endpoint)

    # --- 数据抓取 ---
    async def extract_table(self) -> list[list[str]]:
        """从页面提取所有 HTML 表格数据"""
        return await self.page.evaluate("""
            () => {
                const tables = document.querySelectorAll('table');
                const allRows = [];
                tables.forEach(table => {
                    table.querySelectorAll('tr').forEach(row => {
                        const cells = row.querySelectorAll('td, th');
                        const rowData = Array.from(cells).map(c => c.textContent.trim());
                        if (rowData.length >= 3) allRows.push(rowData);
                    });
                });
                return allRows;
            }
        """)


# ============================================================
# 1. Chrome 启动器（交互式场景）
# ============================================================

def launch_chrome(target_url: str = "about:blank",
                  chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  port: int = 9222):
    """启动带调试端口的 Chrome 并返回进程对象"""
    import subprocess, time, os

    subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'],
                   capture_output=True, text=True)
    time.sleep(2)

    temp_dir = os.path.expandvars(r'%TEMP%\chrome_debug_profile')

    proc = subprocess.Popen([
        chrome_path,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={temp_dir}',
        '--no-first-run',
        '--no-default-browser-check',
        target_url,
    ])
    time.sleep(3)
    return proc


# ============================================================
# 2. 通用探索流程
# ============================================================

async def explore_site(agent: BrowserAgent, start_url: str,
                       search_keywords: list[str],
                       entry_keywords: list[str] = None):
    """
    通用站点探索:
    1. 打开主页
    2. 查找入口链接
    3. 搜索目标关键词
    4. 返回链接地图
    """
    print(f"[探索] {start_url}")
    await agent.goto(start_url, wait=4)

    # 截图存证
    await agent.screenshot("00_homepage")

    # 提取页面文本
    text = await agent.text(3000)
    print(f"  页面标题: {await agent.title()}")
    print(f"  文本长度: {len(text)} chars")

    # 查找入口
    if entry_keywords:
        entries = await agent.find_links(entry_keywords)
        print(f"  入口链接: {len(entries)}")
        for e in entries[:10]:
            print(f"    [{e['text'][:60]}] → {e['href'][:100]}")

    # 搜索目标
    targets = await agent.find_links(search_keywords)
    print(f"  目标链接: {len(targets)}")
    for t in targets[:15]:
        print(f"    [{t['text'][:60]}] → {t['href'][:100]}")

    return targets


# ============================================================
# 3. 数据下载流程
# ============================================================

async def download_via_ui(agent: BrowserAgent,
                          indicator_tree_path: list[str],
                          region: str = "全部",
                          years: str = "最近10年"):
    """
    通过 SPA 界面操作下载数据:
    1. 展开指标树节点
    2. 选择指标
    3. 选择地区
    4. 选择时间
    5. 触发下载
    """
    # Step 1: 逐层展开指标树
    for node_name in indicator_tree_path:
        print(f"  点击: {node_name}")
        clicked = await agent.js_click(node_name)
        if not clicked:
            print(f"    ⚠ 未找到 '{node_name}'")
        await asyncio.sleep(1.5)

    # Step 2: 等待数据加载
    await asyncio.sleep(3)

    # Step 3: 触发下载
    print("  触发下载对话框...")
    download_clicked = await agent.js_click("下载打印")
    if not download_clicked:
        download_clicked = await agent.js_click("下载")

    await asyncio.sleep(2)

    # Step 4: 选择 CSV 并确认（通过 JS 操作弹窗）
    await agent.page.evaluate("""
        () => {
            const labels = document.querySelectorAll('.el-radio');
            for (const label of labels) {
                if (label.textContent.trim() === 'CSV') label.click();
            }
            return new Promise(resolve => {
                setTimeout(() => {
                    const btns = document.querySelectorAll('.el-dialog__footer button');
                    for (const btn of btns) {
                        if (btn.textContent.trim().includes('确认') ||
                            btn.textContent.trim().includes('下载')) {
                            btn.click();
                            resolve(true);
                            return;
                        }
                    }
                    resolve(false);
                }, 500);
            });
        }
    """)
    await asyncio.sleep(3)
    print("  下载已触发")


# ============================================================
# 4. 主流程示例
# ============================================================

async def main():
    agent = BrowserAgent()
    await agent.connect()

    try:
        # --- 示例: 探索中央财经大学图书馆数据库 ---
        print("=" * 60)
        print("Phase 1: 探索图书馆数据库")
        print("=" * 60)

        LIBRARY_DB_URL = "https://lib-443.webvpn.cufe.edu.cn/db/"

        targets = await explore_site(
            agent,
            start_url=LIBRARY_DB_URL,
            search_keywords=[
                'CSMAR', 'CNRDS', 'Wind', '国泰安', '万得', '专利',
                '统计年鉴', '政府采购', 'CNIPA', '国家统计局',
                'iFinD', '同花顺', 'IncoPat', '智慧芽',
            ],
            entry_keywords=['数据库', '电子资源', '中文资源', '数字资源']
        )

        # --- 示例: 进入目标数据库详情页 ---
        print("\n" + "=" * 60)
        print("Phase 2: 数据库详情")
        print("=" * 60)

        for target in targets[:5]:
            href = target['href']
            if 'detail?id=' in href:
                print(f"\n  访问: {target['text'][:60]}")
                await agent.goto(href, wait=2)
                text = await agent.text(2000)
                # 提取关键信息
                for kw in ['资源类型', '采购方式', '用户名', '密码', '访问', 'URL']:
                    for line in text.split('\n'):
                        if kw in line.strip()[:20]:
                            print(f"    {line.strip()[:120]}")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
