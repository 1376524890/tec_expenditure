"""
使用 browser-use Agent + CDP 从 CSMAR 采集税收激励与研发创新数据

目标数据库:
  1. 中国上市公司税收激励与研发创新研究数据库 (试用库, 2026.4.8-6.8)
     → 提供真实的研发费用加计扣除享受额 (当前 rd_tax_deduction 99.8%为负)
  2. 中国上市公司税收研究数据库
     → 提供实际所得税率等税负变量

用法:
  uv run python csmar_collect_tax_incentive.py          # 交互模式: 启动Chrome后暂停让你登录
  uv run python csmar_collect_tax_incentive.py --auto   # 自动模式: 假设已登录,直接开始采集

注意:
  - 需要 DeepSeek API key 有效
  - Chrome 启动后会保留你的 CUFE VPN / CSMAR 登录状态
  - 下载的文件保存到浏览器默认下载目录 (通常是 Downloads)
"""
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from browser_use import Agent, BrowserSession
from browser_use.llm.models import ChatOpenAI

# ============================================================
# 配置
# ============================================================
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_API_KEY = "sk-08327d0ee02b42009948f5067c8dd84a"
DEEPSEEK_MODEL = "deepseek-v4-pro"

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA = r"C:\Users\MarkTom\AppData\Local\Google\Chrome\User Data"
DEBUG_PORT = 9222

CSMAR_URL = "https://data.csmar.com/"
LIBRARY_VPN_URL = "https://lib-443.webvpn.cufe.edu.cn/"

OUTPUT_DIR = Path("D:/科技创新支出/data")


# ============================================================
# Agent 任务指令
# ============================================================
CSMAR_TASK = """你是一个 CSMAR 数据库数据采集助手。请在 CSMAR 平台 (data.csmar.com) 中按以下步骤操作。

## 你已经登录了 CSMAR。现在开始采集。

## 步骤 1: 进入数据中心 → 单表查询
点击页面顶部导航栏的"数据中心"，然后在下拉菜单中点击"单表查询"。
如果页面已经在单表查询界面，跳过此步骤。

## 步骤 2: 查找"试用数据库"
在页面左侧的数据库目录树中，找到并展开"试用数据库"节点。
查看其下是否有:
  - "中国上市公司税收激励与研发创新研究数据库"
  - "中国上市公司税收研究数据库"
如果试用数据库节点不存在或为空，截图并继续步骤4。

## 步骤 3: 下载税收激励数据库的表
对"中国上市公司税收激励与研发创新研究数据库":
  1. 展开该数据库节点，记录所有子表名称
  2. 逐个点击子表进入查询界面
  3. 在字段选择区点击"全选"
  4. 在条件筛选区，设置时间范围: 起始日期 >= 2015-01-01
  5. 点击"查询"或"执行"按钮
  6. 等待数据加载完成 (CSMAR 较慢，耐心等10-20秒)
  7. 点击"导出" → 选择"Excel (.xlsx)"格式
  8. 等待下载完成

对"中国上市公司税收研究数据库"重复以上操作。

## 步骤 4: 检查"公司研究系列" → "上市公司研发创新"
展开"公司研究系列" → "上市公司研发创新"，查看子表列表。
我们已有以下表 (不要重复下载):
  - PT_LCRDSPENDING (研发投入情况表)
  - PT_LCDOMFORAPPLY (国内外专利申请获得情况表)
如果发现有我们未下载的子表 (如政府创新补贴、研发支出明细等)，请下载。

## 步骤 5: 检查下载结果
导航回浏览器的下载页面 (chrome://downloads/)，列出所有最近下载的文件名。
截图保存到 screenshots/ 目录。

## 重要规则
- CSMAR 网站速度较慢，每步操作后等待加载完成再继续
- 导出按钮灰色时 = 数据还在加载，需要等待
- 优先下载税收激励数据库，这是最重要的
- 如果某个数据库无法访问，截图并继续下一个
- 下载文件默认保存在用户的 Downloads 文件夹
"""


def start_chrome(start_url: str = CSMAR_URL):
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
            start_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    print(f"  Chrome PID: {proc.pid}")
    print(f"  CDP URL:    http://127.0.0.1:{DEBUG_PORT}/")
    return proc


async def collect_from_csmar():
    """通过 CDP 连接浏览器，使用 browser-use Agent 采集 CSMAR 数据"""

    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY,
        max_completion_tokens=8192,
        dont_force_structured_output=True,
    )

    cdp_url = f"http://127.0.0.1:{DEBUG_PORT}/"
    session = BrowserSession(cdp_url=cdp_url)

    try:
        await session.start()
        print("已通过 CDP 连接到 Chrome")

        current_title = await session.get_current_page_title()
        current_url = await session.get_current_page_url()
        print(f"当前页面: {current_title}")
        print(f"URL:       {current_url}")

        # 如果不在 CSMAR，尝试导航过去
        if "csmar" not in current_url.lower():
            print("当前不在 CSMAR，正在导航...")
            await session.navigate_to(CSMAR_URL)
            await asyncio.sleep(3)
            new_url = await session.get_current_page_url()
            print(f"导航后 URL: {new_url}")

        # 截图初始状态
        Path("screenshots").mkdir(exist_ok=True)
        await session.take_screenshot(path="screenshots/csmar_01_start.png")
        print("初始截图: screenshots/csmar_01_start.png")

        # 创建 Agent 并执行
        agent = Agent(
            task=CSMAR_TASK,
            llm=llm,
            browser_session=session,
            max_failures=5,
        )

        print("\n" + "=" * 80)
        print("Agent 开始执行 CSMAR 数据采集任务...")
        print("=" * 80)

        result = await agent.run()

        print("\n" + "=" * 80)
        print("Agent 执行完成")
        print("=" * 80)
        print(result)

        # 检查下载的文件
        downloaded = session.downloaded_files
        if downloaded:
            print(f"\n本次会话下载了 {len(downloaded)} 个文件:")
            for f in downloaded:
                print(f"  {f}")
        else:
            print("\n未检测到下载文件。请检查浏览器下载列表。")

        return result

    finally:
        await session.stop()
        print("CDP 会话已断开，Chrome 保持运行。")


async def main():
    auto_mode = "--auto" in sys.argv

    print("=" * 80)
    print("CSMAR 税收激励与研发创新数据采集 (browser-use + CDP)")
    print("=" * 80)

    # 启动 Chrome (打开 CSMAR，用户已有登录 cookie 则自动登录)
    start_chrome(CSMAR_URL)

    if not auto_mode:
        print()
        print("!" * 80)
        print("请在 Chrome 窗口中确认: ")
        print("  1. 已登录 CSMAR (data.csmar.com)")
        print("  2. 如果 CSMAR 需要通过图书馆 VPN，请手动操作")
        print()
        print("准备好后按 Enter 开始自动采集...")
        print("!" * 80)
        input()

    await collect_from_csmar()

    print()
    print(f"下载完成后，请将 .zip/.xlsx 文件移动到: {OUTPUT_DIR}")
    print("然后运行分析脚本检查新数据。")


if __name__ == "__main__":
    asyncio.run(main())
