# -*- coding: utf-8 -*-
"""
URL 验证器节点 - src/agents/nodes/url_validator_node.py

【本节点的核心使命】：省钱、提速、保纯度。
【工作流位置】：位于"搜索节点"之后，"爬虫节点"之前。
【业务痛点】：搜索引擎返回的 URL 经常是列表页、搜索页甚至死链。

【三重漏斗过滤】：
    第一重（物理探针）：HEAD 请求检查存活（404/410 直接丢弃）
    第二重（格式硬校验）：URL 结构判断（确定性，不依赖 LLM）
    第三重（语义大脑）：LLM 阅读摘要判断（补充验证）
"""

import httpx
from typing import Dict, Tuple

from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.config import get_llm_client, get_proxy
from src.utils.prompt_loader import load_prompt


# ============================================================
# 模块 1：LLM 输出 Schema
# ============================================================
class URLValidationResult(BaseModel):
    """LLM 验证结果，包含 4 个固定字段"""
    is_valid_job_detail_page: bool = Field(description="是否为有效的职位详情页")
    reason: str = Field(description="判断理由")
    corrected_company: str = Field(description="更正后的公司名称")
    corrected_url: str = Field(description="更准确的详情页 URL")


# ============================================================
# 模块 2：第一重漏斗 - 物理探针
# ============================================================
def check_url_accessibility(url: str, timeout: float = 5.0) -> Tuple[bool, int | None]:
    """HEAD 请求检查 URL 是否存活"""
    proxy = get_proxy()
    try:
        with httpx.Client(proxy=proxy, timeout=timeout, follow_redirects=True) as client:
            response = client.head(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            status_code = response.status_code
            if status_code in (404, 410):
                return False, status_code
            return True, status_code
    except httpx.TimeoutException:
        return False, 408
    except httpx.RequestError:
        return False, None
    except Exception:
        return False, None


# ============================================================
# 模块 3：第二重漏斗 - URL 格式硬校验（确定性）
# ============================================================
def is_detail_page_by_url(url: str) -> Tuple[bool, str]:
    """
    通过 URL 结构判断是否为职位详情页。
    规则与 evaluator_system.md 保持一致。
    """
    url_lower = url.lower()

    # ----- BOSS直聘 -----
    if "zhipin.com" in url_lower:
        if "/job_detail/" in url_lower and url_lower.endswith(".html"):
            return True, "BOSS详情页，含/job_detail/和.html"
        return False, f"BOSS直聘非详情页格式"

    # ----- 实习僧 -----
    if "shixiseng.com" in url_lower:
        if "/intern/" in url_lower:
            return True, "实习僧详情页，含/intern/"
        return False, f"实习僧非详情页格式"

    # ----- 牛客网 -----
    if "nowcoder.com" in url_lower:
        if "/jobs/detail/" in url_lower:
            return True, "牛客详情页，含/jobs/detail/"
        return False, f"牛客非详情页格式"

    # ----- 猎聘 -----
    if "liepin.com" in url_lower:
        if "/position_detail/" in url_lower:
            return True, "猎聘详情页，含/position_detail/"
        return False, f"猎聘非详情页格式"

    # ----- 拉勾 -----
    if "lagou.com" in url_lower or "liegou.com" in url_lower:
        if "/job_detail/" in url_lower:
            return True, "拉勾详情页，含/job_detail/"
        return False, f"拉勾非详情页格式"

    # ----- 未知平台 -----
    return False, f"未知招聘平台"

# ============================================================
# 模块 4：第三重漏斗 - LLM 语义验证
# ============================================================
def _get_validator_prompt() -> str:
    """获取验证器 System Prompt"""
    try:
        return load_prompt("url_validator_system")
    except Exception:
        return """你是专业的 URL 过滤器。根据 URL、标题和摘要，判断是否为职位详情页。
剔除：公司首页、职位列表页、论坛帖、新闻文章。严格按 JSON 格式输出。"""


def validate_url_with_llm(url: str, title: str = "", snippet: str = "") -> URLValidationResult:
    """LLM 阅读摘要，判断页面属性"""
    llm = get_llm_client()
    structured_llm = llm.with_structured_output(URLValidationResult)
    system_prompt = _get_validator_prompt()

    user_content = f"""请验证以下 URL 是否为有效的职位详情页：

URL: {url}
标题: {title}
摘要: {snippet}

请严格判断并返回 JSON 结果。"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    try:
        return structured_llm.invoke(messages)
    except Exception as e:
        print(f"  [URL验证异常] {url}: {e}")
        return URLValidationResult(
            is_valid_job_detail_page=False,
            reason=f"验证失败: {str(e)}",
            corrected_company="",
            corrected_url=""
        )


# ============================================================
# 模块 5：主节点 - LangGraph 入口
# ============================================================
def url_validator_node(state: AgentState) -> Dict:
    """
    URL 验证节点主函数。
    接收搜索结果，通过三重漏斗过滤后输出有效 URL。
    """
    current_new_urls = state.get("current_new_urls", [])
    search_snippets = state.get("current_search_snippets", [])

    if not current_new_urls:
        return {"validated_urls": [], "url_validation_results": []}

    validated_results = []
    valid_urls = []

    for i, url in enumerate(current_new_urls):
        # 获取对应的摘要信息
        title = ""
        snippet = ""
        if i < len(search_snippets):
            snippet_data = search_snippets[i]
            title = snippet_data.get("title", "")
            snippet = snippet_data.get("snippet", "")

        # ----- 第一重漏斗：物理探针 -----
        is_accessible, status_code = check_url_accessibility(url)
        if not is_accessible:
            print(f"  [URL预检] {url} -> 死链 ({status_code})，丢弃。")
            validated_results.append({
                "url": url, "is_valid": False,
                "reason": f"HTTP {status_code}，页面不可访问",
                "corrected_company": "", "corrected_url": ""
            })
            continue

        # ----- 第二重漏斗：URL 格式硬校验 -----
        is_detail_format, format_reason = is_detail_page_by_url(url)
        if not is_detail_format:
            print(f"  [URL格式拦截] {url} -> {format_reason}")
            validated_results.append({
                "url": url, "is_valid": False,
                "reason": format_reason,
                "corrected_company": "", "corrected_url": ""
            })
            continue

        # ----- 第三重漏斗：LLM 语义验证 -----
        result = validate_url_with_llm(url, title, snippet)
        validated_results.append({
            "url": url,
            "is_valid": result.is_valid_job_detail_page,
            "reason": result.reason,
            "corrected_company": result.corrected_company,
            "corrected_url": result.corrected_url
        })

        if result.is_valid_job_detail_page:
            valid_urls.append(url)

    print(f"  [URL验证] 搜索发现 {len(current_new_urls)} 个URL，通过三重验证存活: {len(valid_urls)} 个")

    return {
        "validated_urls": valid_urls,
        "url_validation_results": validated_results,
    }
