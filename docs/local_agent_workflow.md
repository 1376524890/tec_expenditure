# 本地 Agent 运行步骤与 Prompt 建模

## 概述

本方案使用 **本地 Chrome + Playwright CDP 连接** 替代 browser-use 云端 API，实现对受身份认证保护的学术数据库（图书馆 VPN、CSMAR、国家统计局等）的自动化数据采集。

核心架构：
```
Python (Playwright) → CDP (ws://127.0.0.1:9222) → Chrome (带用户登录态)
```

---

## 一、环境初始化

### 1.1 依赖安装

```bash
uv init --name browser-use-project
uv add browser-use playwright openpyxl pandas
```

### 1.2 启动带调试端口的 Chrome

```python
import subprocess, time

# 终止已有 Chrome
subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], capture_output=True)
time.sleep(2)

# 启动带 CDP 调试端口的 Chrome（独立数据目录避免配置锁）
proc = subprocess.Popen([
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    '--remote-debugging-port=9222',
    f'--user-data-dir={temp_dir}',  # 独立临时目录
    '--no-first-run',
    '--no-default-browser-check',
    'https://target-url.com/',
])
```

**关键点**：使用独立 `--user-data-dir` 而非用户主配置目录，避免 Chrome 文件锁导致 `shutil.copytree` 失败。

### 1.3 验证 CDP 端点

```python
import urllib.request, json
resp = urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=5)
data = json.loads(resp.read())
# → {"Browser": "Chrome/148.0.7778.168", "webSocketDebuggerUrl": "ws://..."}
```

---

## 二、Agent 连接模型

### 2.1 连接方式

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222/')
    page = browser.contexts[0].pages[0]
```

**为什么用 Playwright 而非 browser-use 的 BrowserSession**：
- `BrowserSession(cdp_url=...)` 在 Windows 上存在 CDP WebSocket 重连问题
- `BrowserSession.start()` 尝试复制 Chrome 用户目录导致文件锁错误
- Playwright 的 `connect_over_cdp` 更稳定，直接复用已有浏览器会话

### 2.2 页面操作模式

```python
# 导航
await page.goto(url)
await asyncio.sleep(3)  # SPA 需等待渲染

# 提取文本
text = await page.evaluate('document.body.innerText')

# 执行 JS（带编码安全处理）
result = await page.evaluate('''() => {
    const links = document.querySelectorAll('a');
    return Array.from(links).map(a => ({
        text: (a.textContent || '').trim().substring(0, 100),
        href: a.href
    }));
}''')

# 截图存证
await page.screenshot(path='screenshots/step_N.png', full_page=True)
```

---

## 三、Prompt 设计模式

### 3.1 分层探索 Prompt

**第一层：环境探测** — 不假设页面结构，先获取全局信息
```
"打开目标页面，获取页面标题、URL、全部可见文本和可交互元素列表"
```

**第二层：关键词匹配** — 根据已知术语查找入口
```
"在页面中搜索包含 ['数据库', 'CSMAR', '专利'] 等关键词的链接，列出 text + href"
```

**第三层：逐层深入** — 对每个入口依次导航并提取详情
```
"依次访问每个数据库详情页，提取：资源类型、采购方式、访问地址、账号密码"
```

### 3.2 数据抓取 Prompt 模式

**模式 A：页面文本提取 + 正则解析**
```
"获取页面 innerText，按行解析，找到表头行（含'指标 地区 年份'），提取后续数据行"
```
适用：后端渲染页面、SPA 初始状态

**模式 B：JS DOM 遍历**
```
"querySelectorAll('table tr') 遍历行，提取 td 文本，过滤含数值的行"
```
适用：标准 HTML 表格

**模式 C：API 拦截**
```
"在 page.on('response') 中监听所有含 'query'/'api' 的 JSON 响应，捕获数据端点"
```
适用：SPA 内部有数据 API

**模式 D：fetch 代理（绕过 WAF）**
```
"在 page.evaluate 内用 fetch(url, {credentials: 'include'}) 调用同源 API"
```
适用：API 有 WAF 但浏览器 Session 可豁免

### 3.3 交互操作 Prompt 模式

**问题：SPA 组件不可见/不可点击**
```
"用 JS clickByText 函数遍历 DOM 找 textContent 匹配的元素并触发 click()，
 避免 Playwright 的 locator.click() 因 visibility check 超时"
```

**问题：Vue/Element UI 虚拟滚动下拉框**
```
"直接操作 Vue 实例：document.querySelector('.el-select').__vue__ 或 
 通过 dispatchEvent 模拟用户交互"
```

**问题：下载对话框按钮不可见**
```
"用 page.evaluate 执行 JS：找到 .el-dialog__footer button，直接 .click()"
```

---

## 四、完整工作流程

### Step 1: 信息检索阶段

```
输入: 图书馆 VPN URL + 数据库名称列表
操作:
  1. navigate_to(LIBRARY_URL)
  2. 提取所有 <a> 标签 → 构建 site_map
  3. 按关键词匹配目标数据库 → 构建 target_list
  4. 逐个 navigate_to(数据库详情页)
  5. 提取访问方式、URL、账号密码
输出: 数据库可用性矩阵 (名称、访问方式、状态)
```

### Step 2: 登录与认证阶段

```
输入: target_list 中标记为"需登录"的数据库
操作:
  1. navigate_to(数据库登录页)
  2. 检测页面状态 (已登录/需登录/维护中)
  3. 若需登录: 暂停自动化，提示用户手动登录
  4. 登录后: navigate_to(数据查询页)
输出: 各数据库可访问状态
```

### Step 3: 数据发现阶段

```
输入: 已登录的数据库查询界面
操作:
  1. 提取指标树/分类列表
  2. 按目标变量名匹配（如"科学技术支出"）
  3. 展开分类 → 获取子指标列表
  4. 选择指标 → 观察数据表格是否加载
输出: 可用指标清单 + 数据结构预览
```

### Step 4: 数据下载阶段

```
输入: 已确认可用的指标 + 地区 + 年份
策略链（按优先级尝试）:
  A. 直接调用数据 API (requests/easyquery)
     → 如返回 403，跳过
  B. 浏览器 fetch 代理 (page.evaluate + fetch)
     → 如仍被 WAF 拦截，跳过
  C. UI 交互下载 (点击选择器 → 选择参数 → 点击下载)
     → 如组件不可见/不可点击
  D. JS 强制操作 (element.click() via evaluate)
     → 如弹窗/下载不触发
  E. DOM 直接抓取 (从已渲染的页面文本解析)
     → 最后手段，需多次翻页
输出: CSV/Excel 原始数据文件
```

### Step 5: 数据整理阶段

```
输入: 原始下载文件 (CSV/Excel)
操作:
  1. 识别每个文件的指标名称（通过数值范围交叉验证）
  2. 统一格式：地区 × 年份 面板
  3. 重命名变量 → 与论文字段名对齐
  4. 合并多源数据 (省级 + 企业级)
  5. 构造派生变量 (政策虚拟、交互项、比率)
  6. 生成数据清单 → 标记完成/缺失/待补充
输出: 最终分析面板 + 数据来源对照表
```

---

## 五、关键对抗策略

### 5.1 反自动化对抗

| 障碍 | 表现 | 解决方案 |
|------|------|---------|
| WAF (Web防火墙) | API 返回 403 + Client IP | 浏览器内 fetch（带 Cookie 同源） |
| 证书错误 | `ERR_CERT_DATE_INVALID` | 通过 VPN 代理访问 |
| SPA 搜索框只读 | `input[readonly]` 无法 fill | JS 直接触发组件事件 |
| el-select 不可见 | Playwright visibility check 失败 | `page.evaluate` JS 直接点击 |
| 弹窗遮挡 | 公告弹窗阻挡交互 | 先检测并关闭弹窗 |
| 下载超时 | 异步导出无 download 事件 | JS 点击 + 等待 + 检测文件系统 |

### 5.2 编码问题

```python
# Windows GBK 终端输出中文
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Excel 文件读写
pd.read_excel(path)  # openpyxl 自动处理
df.to_csv(path, encoding='utf-8-sig')  # BOM 兼容 Excel
```

### 5.3 网络稳定性

```python
# 每次导航后等待 SPA 渲染
await page.goto(url)
await asyncio.sleep(3 + extra)  # SPA 需更长等待

# 超时处理
await page.goto(url, timeout=15000)  # 15秒超时
```

---

## 六、自动化程度判定

```
完全自动化: 无需用户干预
  ✅ 公开数据 API 调用
  ✅ DOM 数据抓取
  ✅ 文件下载与解析

半自动化: 需用户单次操作
  ⚠️ 登录认证（用户输入密码）
  ⚠️ 验证码（用户完成验证）
  ⚠️ SPA 文件下载对话框（用户点击确认）

手动操作: 用户自行完成
  ❌ CSMAR 复杂查询界面（多层嵌套选择器）
  ❌ 国家统计局分省数据选择（需逐个省份勾选）
```

---

## 七、复现命令

```bash
# 1. 环境
cd D:\科技创新支出
uv sync

# 2. 启动 Chrome
python -c "
import subprocess, time
subprocess.run(['taskkill','/F','/IM','chrome.exe'], capture_output=True)
time.sleep(2)
subprocess.Popen([
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    '--remote-debugging-port=9222',
    r'--user-data-dir=%TEMP%\chrome_debug_profile',
    '--no-first-run',
])
"

# 3. 验证 CDP
python -c "
import urllib.request, json
r = urllib.request.urlopen('http://127.0.0.1:9222/json/version')
print(json.loads(r.read())['Browser'])
"

# 4. 运行采集脚本
uv run python merge_final.py
```
