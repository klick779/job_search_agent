# -*- coding: utf-8 -*-
"""
状态定义模块 - src/agents/state.py
该文件定义了 LangGraph 全局执行状态（GraphState）和单个招聘岗位的结构化数据模型（JobInfo）。
"""

from pydantic import BaseModel, Field
from typing import List, Dict, TypedDict, Annotated
import operator


class JobInfo(BaseModel):
    """
    单条招聘岗位信息的结构化模型。
    作用：强制大模型输出标准 JSON 格式的岗位数据，确保字段完整性和类型安全。
    效果：通过 Pydantic 的 Field description 向 LLM 传达字段语义，提高抽取准确性。
    """
    
    # 职位名称
    title: str = Field(description="职位名称")
    
    # 公司或组织名称
    company: str = Field(description="公司名称")
    
    # 工作地点，如 '北京', '上海', '远程'
    location: str = Field(description="工作地点")
    
    # 薪资范围，如 '20k-40k' 或 '面议'
    salary: str = Field(description="薪资范围")
    
    # 从JD中抽取的技术关键词标签
    tech_tags: List[str] = Field(description="技术关键词")
    
    # 提炼出的岗位核心技能与业务要求摘要，限100字以内
    requirements: str = Field(description="岗位核心技能摘要")
    
    # 数据来源的招聘网站名称，如 'Boss直聘', '牛客网', '拉勾'
    source: str = Field(description="招聘网站")
    
    # 该岗位的原始来源网页链接
    job_url: str = Field(description="岗位链接")
    
    # 布尔类型，核心语义判断：是否为真正的 AI Engineer 且面向校招/实习生
    # 作用：这是系统最核心的语义筛选字段
    is_valid_ai_role: bool = Field(
        description="布尔类型，核心语义判断：是否符合岗位要求，且面向校招/实习生"
    )


class AgentState(TypedDict):
    """
    LangGraph 运行时的全局状态上下文变量。
    作用：作为整个 Agent 网络共享的"白板"，每个节点执行完毕后将其计算结果写回全局状态，
         供后续节点读取与消费。
    效果：通过 Annotated[..., operator.add] 实现状态累加而非覆盖，支持循环迭代逻辑。
    """
    
    # 目标收集的岗位数量
    # 作用：设定任务完成标准，通常为 50
    target_count: int
    
    # 已收集的有效岗位列表
    # 作用：存储通过语义筛选的合格岗位，累积直到达到目标数量
    # 效果：新收集的岗位会追加到列表末尾
    collected_jobs: Annotated[List[Dict], operator.add]
    
    # 当前搜索查询列表
    # 作用：存储本次迭代要执行的搜索关键词
    current_search_queries: List[str]
    
    # 已使用过的搜索查询历史
    # 作用：防止 Agent 重复搜索相同的关键词，避免陷入死循环
    # 效果：新使用的查询会追加到历史记录中
    used_queries: Annotated[List[str], operator.add]
    
    # 已访问/抓取过的 URL 列表
    # 作用：去重处理，避免对同一页面重复抓取
    visited_urls: Annotated[List[str], operator.add]
    
    # 本轮新发现的 URL 列表
    # 作用：只抓取本轮新发现的 URL，避免重复抓取历史 URL
    current_new_urls: List[str]
    
    # 已抓取并解析的网页内容列表
    # 作用：存储爬虫获取的 Markdown 内容，供语义评估器处理
    scraped_markdowns: List[Dict]
    
    # 当前循环迭代次数
    # 作用：追踪 Agent 执行轮数，是防御无限死循环机制的关键
    # 效果：每次进入新迭代时自动 +1
    loop_count: int
    
    # =============== 定向搜索策略相关字段 ===============
    # 作用：实现"多网站策略切换"机制，当一个网站搜不到时自动切换到下一个
    
    # 招聘网站白名单
    allowed_sites: List[str]
    
    # 当前正在搜索的网站索引
    current_site_index: int
    
    # 已抓取过的 URL 列表（搜索去重用）
    scraped_urls: List[str]
