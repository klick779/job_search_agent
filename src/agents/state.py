# -*- coding: utf-8 -*-
"""
状态定义模块
LangGraph 全局执行状态和单个招聘岗位的结构化数据模型
"""

from pydantic import BaseModel, Field
from typing import List, Dict, TypedDict, Annotated, NotRequired
import operator


class JobInfo(BaseModel):
    """单条招聘岗位信息的结构化模型"""
    title: str = Field(description="职位名称")
    company: str = Field(description="公司名称")
    location: str = Field(description="工作地点")
    salary: str = Field(description="薪资范围")
    tech_tags: List[str] = Field(description="技术关键词")
    requirements: str = Field(description="岗位核心技能摘要")
    source: str = Field(description="招聘网站")
    job_url: str = Field(description="岗位链接")
    is_valid_role: bool = Field(description="是否符合用户期望的岗位类型，且面向校招/实习生")


class AgentState(TypedDict):
    """LangGraph 运行时的全局状态"""
    # 用户输入
    user_input: NotRequired[str]
    
    # 意图解析结果
    target_role: NotRequired[str]
    search_keywords: NotRequired[List[str]]
    
    # 搜索相关
    target_count: int
    collected_jobs: Annotated[List[Dict], operator.add]
    current_search_queries: List[str]
    used_queries: Annotated[List[str], operator.add]
    visited_urls: Annotated[List[str], operator.add]
    current_new_urls: List[str]
    current_search_snippets: NotRequired[List[Dict]]  # 新增：搜索结果摘要
    scraped_markdowns: List[Dict]
    loop_count: int
    allowed_sites: List[str]
    current_site_index: int
    scraped_urls: List[str]
    
    # URL 验证相关（新增）
    validated_urls: NotRequired[List[str]]
    url_validation_results: NotRequired[List[Dict]]
