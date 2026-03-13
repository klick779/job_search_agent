# Agentic AI 自动化求职助手系统

## 项目简介

本系统是一个基于 **Agentic AI** 架构的自动化求职助手，采用 **LangGraph** 多智能体框架实现。系统根据用户输入的任意岗位类型，自动完成意图解析、搜索关键词生成、岗位搜索、URL 有效性验证、网页内容抓取、语义评估等全流程，最终输出结构化的校园招聘/实习岗位数据。

---

## 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 多智能体框架 | **LangGraph** | 基于图状态机的多节点编排 |
| LLM 应用框架 | **LangChain** | Prompt 模板、输出解析、结构化调用 |
| 大语言模型 | **OpenAI GPT-4o** | 语义理解、内容解析、URL 验证 |
| 网页搜索 | **Tavily** | 实时搜索招聘网站 |
| 网页抓取 | **Crawl4AI** | AI 驱动的网页内容提取 |
| 前端界面 | **Gradio** | 交互式聊天界面 |
| 环境配置 | **python-dotenv** | 环境变量管理 |

---

## 项目结构

```
.
├── prompts/                              # 📝 LLM 提示词（运行时动态加载）
│   ├── evaluator_system.md                # 语义评估器 System Prompt
│   ├── evaluator_user.md                  # 语义评估器 User 模板
│   ├── query_planner_system.md            # 查询规划器 System Prompt
│   ├── intent_parser_system.md            # 意图解析器 System Prompt
│   └── url_validator_system.md            # URL 验证器 System Prompt
│
├── src/                                   # 📦 核心源代码
│   ├── __init__.py
│   │
│   ├── config.py                          # ⚙️ 全局配置（API Key、LLM 参数、工程参数）
│   │
│   ├── agents/                            # 🤖 Agent 核心模块
│   │   ├── __init__.py
│   │   ├── state.py                       # 📋 状态定义（AgentState、JobInfo）
│   │   ├── graph.py                       # 🕸️ LangGraph 图编排与条件路由
│   │   ├── runner.py                      # 🏃 工作流运行入口
│   │   │
│   │   └── nodes/                         # 📍 LangGraph 节点实现
│   │       ├── __init__.py
│   │       ├── intent_parser_node.py      # 🎯 意图解析：提取目标岗位、数量
│   │       ├── query_planner_node.py      # 📝 查询规划：生成搜索关键词
│   │       ├── job_searcher_node.py       # 🔍 岗位搜索：调用 Tavily
│   │       ├── url_validator_node.py      # ✅ URL 验证：过滤无效链接
│   │       ├── detail_scraper_node.py     # 🕷️ 详情抓取：使用 Crawl4AI
│   │       └── semantic_evaluator_node.py# 🧠 语义评估：LLM 判断岗位有效性
│   │
│   ├── tools/                             # 🛠️ 工具模块
│   │   ├── __init__.py
│   │   ├── search_tool.py                 # 搜索工具封装
│   │   ├── scraper_tool.py                # 抓取工具封装
│   │   └── parser_tool.py                 # 解析工具（调用 LLM）
│   │
│   └── utils/                             # 🧰 工具函数
│       ├── __init__.py
│       ├── prompt_loader.py               # 动态加载提示词
│       └── output_formatter.py            # 输出格式化（CSV/JSON）
│
├── app_chat.py                            # 🎨 Gradio 聊天界面入口
├── requirements.txt                       # 📌 Python 依赖
└── .env                                   # 🔐 环境变量（需手动创建）
```

### 节点详细说明

| 序号 | 节点 | 输入 | 输出 | 核心功能 |
|------|------|------|------|----------|
| 1 | `intent_parser_node` | 用户原始输入 | `target_role`, `target_count`, `keywords` | 解析用户意图，提取目标岗位类型、数量 |
| 2 | `query_planner_node` | 意图解析结果 | `search_queries` | 生成多样化搜索关键词 |
| 3 | `job_searcher_node` | 搜索关键词 | `search_results` (URL列表) | 调用 Tavily 搜索招聘网站 |
| 4 | `url_validator_node` | URL 列表 | `validated_urls` | LLM 判断是否为有效职位详情页 |
| 5 | `detail_scraper_node` | 有效 URL | `scraped_contents` | 使用 Crawl4AI 抓取页面内容 |
| 6 | `semantic_evaluator_node` | 页面内容 | `collected_jobs` | LLM 判断岗位是否符合要求，提取信息 |
| 7 | `check_completion` | 已收集岗位数 | 路由决策 | 检查是否达到目标或超出轮数 |

---

## 快速开始

### 1. 环境要求

- Python 3.12+
- macOS / Linux / Windows

### 2. 创建虚拟环境

```bash
python3.12 -m venv homework
source homework/bin/activate  # macOS / Linux
# homework\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 初始化 Crawl4AI

```bash
crawl4ai-setup
```

### 5. 配置环境变量

创建 `.env` 文件：

```bash
# OpenAI API Key（必须）
# 获取地址: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-xxxxxxxxxxxx

# Tavily API Key（搜索必须）
# 获取地址: https://app.tavily.com/api-keys
TAVILY_API_KEY=tvly-xxxxxxxxxxxx

# 代理配置（可选，如需翻墙）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

### 6. 运行系统

```bash
python app_chat.py
```

浏览器访问 **http://127.0.0.1:7860** ，在输入框输入求职需求：

```
我想找交通运输岗位50条
帮我搜20条机械工程师实习
找数据科学岗位10条
```

---

## 输出结果

系统运行完成后，在当前目录生成：

| 文件 | 格式 | 说明 |
|------|------|------|
| `Jobs.csv` | CSV (utf-8-sig) | 便于 Excel 打开 |
| `Jobs.json` | JSON | 便于程序处理 |
