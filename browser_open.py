"""
使用 browser-use 打开浏览器，访问 NBS 数据浏览器采集省级数据
LLM 后端: DeepSeek OpenAI 兼容接口
"""
import asyncio
import os
from pathlib import Path
from browser_use import Agent
from browser_use.llm.models import ChatOpenAI

# DeepSeek OpenAI 兼容端点
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_API_KEY = "sk-08327d0ee02b42009948f5067c8dd84a"
DEEPSEEK_MODEL = "deepseek-v4-pro"

async def open_browser_and_collect():
    """使用 browser-use 打开浏览器"""

    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY,
        max_completion_tokens=8192,
        dont_force_structured_output=True,
    )

    task = """
你是一个数据采集助手。请按以下步骤操作：

1. 打开浏览器，访问 https://data.stats.gov.cn/easyquery.htm?cn=E0103
   这是国家统计局的分省年度数据查询页面。

2. 等待页面完全加载（可能需要几秒，这是政府网站）。

3. 在页面左侧的指标树中，尝试找到"科技"或"研究与试验发展"相关的指标。
   如果指标树没有加载，尝试使用页面上的搜索框搜索"R&D经费内部支出"或"研究与试验发展经费"。

4. 如果找到了指标：
   - 勾选该指标
   - 在地区维度选择全部31个省份
   - 在时间维度选择2017-2023年
   - 点击查询按钮
   - 查看返回的表格数据

5. 如果以上方案不可行（例如网站需要特定浏览器或IP），请：
   - 截图当前页面状态
   - 报告具体原因
   - 尝试替代方案：访问 https://www.stats.gov.cn/sj/ndsj/2023/indexch.htm 查看年中国统计年鉴

6. 最后报告你看到了什么，以及能否获取数据。

请认真执行每一步，不要跳过。如果某个步骤失败，说明原因并尝试替代方案。
"""

    agent = Agent(
        task=task,
        llm=llm,
    )

    print("正在启动 browser-use agent...")
    result = await agent.run()
    print("\n" + "=" * 80)
    print("Agent 执行完成")
    print("=" * 80)
    print(result)

    return result


if __name__ == "__main__":
    asyncio.run(open_browser_and_collect())
