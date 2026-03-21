# -*- coding: utf-8 -*-
"""
状态定义模块
LangGraph 全局执行状态和单个招聘岗位的结构化数据模型
"""

# 从 pydantic 导入基础模型类和字段定义工具
from pydantic import BaseModel, Field
# 导入一堆类型提示工具，帮助 IDE 报错和 LangGraph 识别状态
from typing import List, Dict, TypedDict, Annotated, NotRequired
import operator  # 导入基础操作符，主要为了用 operator.add


class JobInfo(BaseModel):
    """单条招聘岗位信息的结构化模型"""
    # 继承 BaseModel 后，下面的每一个属性都会被 Pydantic 严格审查类型。
    # Field(description="...") 是写给大模型看的！大模型在提取网页信息时，会读取这些 description 来理解字段含义。
    title: str = Field(description="职位名称")
    company: str = Field(description="公司名称")
    location: str = Field(description="工作地点")
    salary: str = Field(description="薪资范围")
    tech_tags: List[str] = Field(description="技术关键词") # 比如 ["Python", "LangChain", "LLM"]
    requirements: str = Field(description="岗位核心技能摘要")
    source: str = Field(description="招聘网站")
    job_url: str = Field(description="岗位链接")
    # 这是一个布尔值（True/False），用来让大模型判断这个岗位是不是我们要找的校招/实习
    is_valid_role: bool = Field(description="是否符合用户期望的岗位类型，且面向校招/实习生")


class AgentState(TypedDict):
    """
    LangGraph 运行时的全局状态
    你可以把它想象成一个大字典，Agent 每执行完一个动作，就会更新这个字典里的内容。
    """
    
    # 1. 用户输入
    # NotRequired 表示刚启动时可能没有这个值，是合法的。
    user_input: NotRequired[str] 
    
    # 2. 意图解析结果（大模型分析用户输入后得出的结论）
    target_role: NotRequired[str]           # 目标岗位，比如 "Python后端开发实习生"
    search_keywords: NotRequired[List[str]] # 拆解出的搜索关键词，比如 ["Python", "实习", "杭州"]
    
    # 3. 搜索与执行过程中的动态数据
    target_count: int                       # 我们目标要抓取多少个岗位（比如从 Config 里读取的 50）
    
    # 【Annotated 与 operator.add】
    # 正常的字典更新是“覆盖”。但在这里，我们希望每次找到新岗位时，是“追加”到列表中！
    # Annotated[List[Dict], operator.add] 的意思就是告诉 LangGraph：
    # “如果有新数据进来，请用加法（追加）和旧数据合并，千万别把旧数据覆盖掉！”
    collected_jobs: Annotated[List[Dict], operator.add] 
    
    current_search_queries: List[str]       # 当前这一轮准备去搜索引擎里搜的词
    
    # 记录已经搜过的词，防止 Agent 变傻一直在原地重复搜索（累加模式）
    used_queries: Annotated[List[str], operator.add] 
    
    # 记录已经访问过的网页链接，防止重复爬取（累加模式）
    visited_urls: Annotated[List[str], operator.add] 
    
    current_new_urls: List[str]             # 这一轮刚刚从搜索引擎里提取出的新链接
    
    # 新增：搜索引擎返回的结果摘要，作为中间过渡数据，可有可无
    current_search_snippets: NotRequired[List[Dict]]  
    
    scraped_markdowns: List[Dict]           # 爬虫抓取网页后，转换成的纯文本（Markdown）内容
    loop_count: int                         # 当前 Agent 已经循环思考了多少次（防止死循环）
    allowed_sites: List[str]                # 允许去哪些招聘网站搜，比如 ["boss.com", "lagou.com"]
    current_site_index: int                 # 当前正在搜索 allowed_sites 里的第几个网站
    scraped_urls: Annotated[List[str], operator.add]   # 当前这一轮成功抓取到内容的 URL 列表
    
    #  URL 验证相关
    validated_urls: NotRequired[List[str]]       # 经过初步校验，看起来像是有效招聘详情页的链接
    url_validation_results: NotRequired[List[Dict]] # URL 校验的具体结果报告