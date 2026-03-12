# Agentic AI 自动化求职助手系统

## 项目简介

本系统是一个基于 Agentic AI 的自动化求职助手，用于自动收集 AI Engineer 校园招聘岗位信息。

## 技术栈

- **LangGraph**: 多智能体编排框架，基于图状态机实现
- **Crawl4AI**: AI 驱动的网页抓取工具，支持反爬虫绕过
- **LangChain**: LLM 应用开发框架
- **OpenAI**: GPT-4o 模型提供语义理解能力
- **Tavily**: 搜索引擎 

## 项目结构

```
homework/
├── src/
│   ├── __init__.py
│   ├── config.py                    # 全局配置
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py                 # 状态定义 (GraphState & JobInfo)
│   │   ├── prompts.py               # 提示词工程
│   │   ├── nodes.py                 # 核心智能体节点
│   │   └── graph.py                 # 图编排与路由
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search_tool.py           # 搜索工具
│   │   ├── scraper_tool.py          # 抓取工具
│   │   └── parser_tool.py           # 解析工具
│   └── utils/
│       ├── __init__.py
│       └── output_formatter.py      # 输出格式化
├── main.py                          # 系统入口
├── requirements.txt                  # 依赖清单
├── .env.example                     # 环境变量示例
└── homework/                        # Python 虚拟环境
```

## 快速开始

### 1. 激活虚拟环境

```bash
cd homework
source homework/bin/activate  # Linux/Mac
# 或
homework\Scripts\activate     # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

打开 `.env`，并填入您的 API Key：

获取 OpenAI API Key: https://platform.openai.com/api-keys

### 4. 初始化 Crawl4AI

```bash
crawl4ai-setup
```

### 5. 运行系统

```bash
python main.py
```

## 输出文件

系统运行完成后会生成以下文件：

- `standardized_ai_jobs.csv`: 标准化 CSV 格式岗位数据
- `standardized_ai_jobs.json`: JSON 格式岗位数据（保留 tech_tags 数组）

## Agent 能力与三大工具

符合作业要求「搜索工具、抓取工具、解析工具」及完整流程：

| 能力 | 说明 | 实现位置 |
|------|------|----------|
| **任务规划** | 将「找到 50 个岗位」拆解为 搜索 → 抓取 → 解析 → 去重 → 存储 | `graph.py` 编排；`nodes.py` 各节点 |
| **工具调用** | 能调用搜索工具、网页抓取工具、信息解析工具 | 见下方三大工具 |
| **迭代搜索** | 岗位数量不足时自动调整关键词继续搜索 | `query_planner_node` + `check_completion_router` |
| **语义判断** | 判断岗位是否属于 AI Engineer 方向（校招/实习） | `parser_tool` + 解析工具内 LLM |
| **数据清洗** | 自动结构化岗位信息（JobInfo） | `parser_tool`、`output_formatter` |
| **结果汇总** | 输出标准化 JSON/CSV | `output_formatter.format_and_save_jobs` |

### 三大工具

1. **搜索工具** `src/tools/search_tool.py`  
   执行网络搜索，获取招聘相关 URL（DuckDuckGo）。Agent 在 `job_searcher_node` 中调用。

2. **抓取工具** `src/tools/scraper_tool.py`  
   网页抓取，获取页面 Markdown（Crawl4AI）。Agent 在 `detail_scraper_node` 中调用。

3. **解析工具** `src/tools/parser_tool.py`  
   将抓取内容解析为结构化岗位信息并做语义判断（LLM + JobInfo）。Agent 在 `semantic_evaluator_node` 中调用。

### 示例工作流程

1. 选择/构造搜索关键词（如 AI Engineer、机器学习工程师、算法工程师）
2. **搜索** → 抓取职位列表/详情页 URL
3. **抓取** → 进入详情页获取页面内容
4. **解析** → 判断是否符合「AI Engineer + 校招/实习」，结构化输出
5. 去重（按 `job_url`）
6. 不足 50 条 → 调整关键词回到步骤 2
7. 输出标准化 JSON/CSV

## 核心功能

1. **任务规划**: 根据已收集数量动态生成搜索策略
2. **多源搜索**: 支持多个招聘网站搜索（搜索工具）
3. **智能爬虫**: 绕过反爬机制抓取页面（抓取工具）
4. **语义筛选**: 解析工具内 LLM 区分真正的 AI Engineer 与普通后端
5. **自动迭代**: 不足 50 条时自动继续搜索
6. **防死循环**: 最大迭代次数保护
7. **去重**: 结果按 URL 去重后再写入文件

## 配置参数

在 `src/config.py` 中可修改：

- `TARGET_JOB_COUNT`: 目标岗位数量
- `MAX_LOOP_COUNT`: 最大迭代次数
- `MAX_SEARCH_RESULTS`: 每次搜索结果数
- `MAX_SCRAPE_PER_ITERATION`: 每次抓取页面数

## 注意事项

1. 请确保已设置有效的 OpenAI API Key
2. 系统会自动处理部分失败，继续执行
3. 首次运行可能需要较长时间初始化
4. 如遇反爬限制，建议等待后重试
