"""
使用 browser-use 自动化采集省级R&D经费支出数据
数据来源: 国家统计局数据浏览器 (data.stats.gov.cn)
采集指标: 研究与试验发展(R&D)经费内部支出（分省年度）
采集年份: 2017-2023
"""
import asyncio
import os
from pathlib import Path
from browser_use import Agent
from langchain_openai import ChatOpenAI

# 使用已有的 OPENAI_API_KEY 或自定义 LLM
# browser-use 默认使用 OpenAI，可以通过环境变量或参数配置

async def collect_provincial_rd_data():
    """使用 browser-use 从国家统计局数据浏览器采集省级R&D经费数据"""

    task = """
你是一个数据采集助手。请按以下步骤在"国家统计局数据浏览器"中采集数据：

1. 访问 https://data.stats.gov.cn/easyquery.htm?cn=E0103

2. 这是"分省年度数据"页面。在左侧指标树中，找到以下路径的指标：
   "科技" → "研究与试验发展(R&D)经费内部支出"
   或者通过搜索框搜索"研究与试验发展经费内部支出"

3. 选择该指标后，在右侧数据区域：
   - 地区选择：全选所有31个省份
   - 时间选择：2017, 2018, 2019, 2020, 2021, 2022, 2023

4. 点击"查询"按钮获取数据

5. 提取显示的表格数据，以CSV格式输出：
   province, year_2017, year_2018, year_2019, year_2020, year_2021, year_2022, year_2023
   北京, ...
   天津, ...
   ... (继续所有31个省)

6. 如果可以直接"导出"为Excel或CSV，请点击导出按钮下载文件。

请仔细执行每一步。如果某个步骤不可行，请说明原因并尝试替代方案。
"""

    # 使用 browser-use Agent
    agent = Agent(
        task=task,
        # browser-use 默认使用 ChatOpenAI，可通过环境变量配置
        # llm=ChatOpenAI(model="gpt-4o"),
    )

    result = await agent.run()
    print("=" * 80)
    print("采集结果:")
    print(result)
    return result


async def collect_from_yearbook():
    """备用方案: 从中国统计年鉴页面逐表采集"""

    task = """
你是一个数据采集助手。请访问中国统计年鉴2023年版的科学技术章节。

1. 访问 https://www.stats.gov.cn/sj/ndsj/2023/indexch.htm

2. 在左侧导航栏中找到"20 科学技术"（第二十章），点击展开

3. 找到表"20-1 研究与试验发展(R&D)经费内部支出"或类似名称的表格链接，点击进入

4. 表格应显示各省份的R&D经费支出数据。提取2017-2022年的数据（注意：2023年年鉴包含的是2022年的数据）。

5. 同样，访问其他年份的年鉴获取对应数据：
   - 2022年年鉴 → 2021年数据: https://www.stats.gov.cn/sj/ndsj/2022/indexch.htm
   - 2021年年鉴 → 2020年数据: https://www.stats.gov.cn/sj/ndsj/2021/indexch.htm
   - 2020年年鉴 → 2019年数据: https://www.stats.gov.cn/sj/ndsj/2020/indexch.htm
   - 2019年年鉴 → 2018年数据: https://www.stats.gov.cn/sj/ndsj/2019/indexch.htm
   - 2018年年鉴 → 2017年数据: https://www.stats.gov.cn/sj/ndsj/2018/indexch.htm

6. 将所有数据汇总为一个CSV表格，包含31个省份 × 6年(2017-2022)的数据。

注意：如果页面使用iframe或frameset，你需要切换到相应的frame中查找表格。
"""

    agent = Agent(task=task)
    result = await agent.run()
    print("=" * 80)
    print("采集结果:")
    print(result)
    return result


if __name__ == "__main__":
    # 首先尝试从数据浏览器采集（更高效）
    print("方案1: 从国家统计局数据浏览器采集...")
    try:
        asyncio.run(collect_provincial_rd_data())
    except Exception as e:
        print(f"方案1失败: {e}")
        print("\n方案2: 从统计年鉴页面采集...")
        try:
            asyncio.run(collect_from_yearbook())
        except Exception as e2:
            print(f"方案2也失败: {e2}")
