# -*- coding: utf-8 -*-
"""
解析工具模块 - src/tools/parser_tool.py
作用：将抓取到的网页原始内容解析为结构化岗位信息，并做语义判断。
效果：输出符合 JobInfo Schema 的结构化数据，供去重与结果汇总使用。
"""

from typing import Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from src.agents.state import JobInfo
from src.config import get_llm_client, config
from src.utils.prompt_loader import load_prompt


# ---------- 评估器提示词 ----------
# 如果外部的 md 文件被误删，系统不会崩溃，而是退化使用内存里的硬编码 Prompt。
def get_evaluator_system_prompt(target_role: str = "通用岗位") -> str:
    """获取评估器 System Prompt"""
    try:
        return load_prompt("evaluator_system", target_role=target_role)
    except Exception:
        # Fallback 兜底方案
        return f"""你是技术招聘审查专家。审核网页信息，判断是否符合用户期望的岗位类型（{target_role}），提取结构化标签。
岗位需面向应届生/校招/实习。检测已下线岗位。
按照 Pydantic Schema 输出 JSON。"""


def get_evaluator_user_template(target_role: str = "通用岗位") -> str:
    """获取评估器 User 模板"""
    try:
        return load_prompt("evaluator_user", target_role=target_role)
    except Exception:
        return f"""分析网页内容，判断是否为符合用户期望岗位类型（{target_role}）的校园招聘/实习岗位。
首先检查是否已下线/已关闭。
网页内容：
---
{{content}}
---
按照 Pydantic Schema 输出。"""


def parse_page_to_job(
    content: str,              # 爬虫刚刚抓回来的，几千字乱糟糟的 Markdown 文本
    url: str,                  # 这个网页对应的网址
    target_role: str = "",     # 用户到底想找啥？（比如 "AI算法工程师"）
    max_content_length: Optional[int] = None,
) -> Optional[Dict]:           # 返回值：要么是一个完美的字典，要么是 None（垃圾数据，不要）
    
    # ---------------- 步骤 1：文本裁剪 ----------------
    # 网页有时候太长了（比如包含了几十条不相关的推荐职位），
    # 喂给大模型太贵了（按字数收钱）。所以我们拿刀切一下，默认只取前 4000 个字。
    length = max_content_length or config.CONTENT_TRUNCATION_LENGTH
    content_to_eval = content[:length] 
    
    # ---------------- 步骤 2：召唤与附魔 ----------------
    # 召唤一个基础的大模型实例（比如 GPT-4o-mini）
    llm = get_llm_client()
    
    # 给这个大模型“附魔”，戴上 JobInfo 的紧箍咒。
    # 从现在起，这个 structured_llm 只会吐出符合 JobInfo 格式的数据。
    structured_llm = llm.with_structured_output(JobInfo)

    # ---------------- 步骤 3：准备话术 ----------------
    # 获取系统面具（把你找 "AI算法工程师" 的需求嵌进去）
    system_prompt = get_evaluator_system_prompt(target_role=target_role)
    # 获取具体的任务卡（把你找 "AI算法工程师" 的需求嵌进去）
    user_template = get_evaluator_user_template(target_role=target_role)

    # 把“面具”和“带有网页正文的任务卡”打包进一个信封（messages）里
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_template.format(content=content_to_eval)),
    ]
    
    # ---------------- 步骤 4：送交大模型审判 ----------------
    try:
        # invoke 就是把信封寄给 OpenAI，然后苦苦等待它回复。
        # 回复的结果直接就是一个 JobInfo 对象！
        job_info: JobInfo = structured_llm.invoke(messages)
        
        # 【裁判吹哨】：大模型在填表时，顺便判断了这个岗位到底是不是 AI 校招岗。
        # 如果大模型觉得“这根本不是 AI 岗”或者“这是个社招岗”，is_valid_role 就会是 False。
        if not job_info.is_valid_role:
            return None # 直接返回 None，也就是告诉主程序：“把这个垃圾扔进垃圾桶！”
            
        # ---------------- 步骤 5：打补丁与交货 ----------------
        # 大模型在阅读正文时，经常找不到这个页面的真实 URL。
        # 没关系，我们作为程序员，手里拿着真实的 url，强行塞进大模型生成的表格里。
        job_info.job_url = url
        
        # 为什么要有 model_dump()？
        # job_info 现在是一个高级的 Pydantic 对象，但后面的程序（比如存 CSV）只认识普通的 Python 字典。
        # model_dump() 就像是把高级跑车拆成了一堆通用零件（字典），方便后续处理。
        return job_info.model_dump()
        
    except Exception as e:
        # 如果大模型抽风了（比如断网、或者死活无法生成正确的 JSON）
        # 我们不能让整个程序崩溃，所以捕获异常。
        print(f"  [解析异常] URL: {url}, 错误: {e}") 
        return None 


def parse_pages_to_jobs(scraped_items: List[Dict], target_role: str = "") -> List[Dict]:
    """
    批量解析多页抓取结果为结构化岗位列表。
    """
    jobs = []
    for item in scraped_items:
        parsed = parse_page_to_job(
            content=item["markdown"], 
            url=item["url"],
            target_role=target_role
        )
        if parsed:
            jobs.append(parsed)
    return jobs