# -*- coding: utf-8 -*-
"""
URL 验证器节点
使用 LLM 验证搜索结果中的 URL 是否为有效的职位详情页
"""

from typing import Dict, List
import httpx
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.config import get_llm_client, get_proxy
from src.utils.prompt_loader import load_prompt


class URLValidationResult(BaseModel):
    """URL 验证结果"""
    is_valid_job_detail_page: bool = Field(description="是否为有效的职位详情页")
    reason: str = Field(description="判断理由")
    corrected_company: str = Field(description="如果能找到，更正后的公司名称")
    corrected_url: str = Field(description="如果原URL不是详情页，提供更准确的职位详情页URL（如有）")


def check_url_accessibility(url: str, timeout: float = 5.0) -> tuple[bool, int | None]:
    """
    使用 HEAD 请求快速检查 URL 是否可访问
    
    参数：
        url: 待检查的 URL
        timeout: 超时时间（秒）
    
    返回：
        (is_accessible, status_code): 是否可访问、HTTP 状态码
    """
    proxy = get_proxy()
    try:
        with httpx.Client(proxy=proxy, timeout=timeout, follow_redirects=True) as client:
            response = client.head(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            status_code = response.status_code
            
            # 2xx 认为可访问，4xx/5xx 认为不可访问
            is_accessible = 200 <= status_code < 400
            return is_accessible, status_code
    except httpx.TimeoutException:
        return False, 408
    except httpx.RequestError:
        return False, None
    except Exception:
        return False, None


def _get_validator_prompt() -> str:
    """获取 URL 验证器提示词"""
    return load_prompt("url_validator_system")


def validate_url_with_llm(url: str, title: str = "", snippet: str = "") -> URLValidationResult:
    """
    使用 LLM 验证 URL 是否为有效的职位详情页
    
    参数：
        url: 待验证的 URL
        title: 搜索结果中的标题（可选）
        snippet: 搜索结果中的摘要（可选）
    
    返回：
        URLValidationResult: 验证结果
    """
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
        result: URLValidationResult = structured_llm.invoke(messages)
        return result
    except Exception as e:
        print(f"  [URL验证异常] {url}: {e}")
        return URLValidationResult(
            is_valid_job_detail_page=False,
            reason=f"验证失败: {str(e)}",
            corrected_company="",
            corrected_url=""
        )


def url_validator_node(state: AgentState) -> Dict:
    """
    URL 验证节点 - 过滤掉非职位详情页的 URL
    
    从搜索结果中筛选出真正指向职位详情页的 URL，
    剔除列表页、公司主页、讨论帖等无效页面。
    """
    current_new_urls = state.get("current_new_urls", [])
    search_snippets = state.get("current_search_snippets", [])
    
    if not current_new_urls:
        return {
            "validated_urls": [],
            "url_validation_results": []
        }
    
    validated_results = []
    valid_urls = []
    
    for i, url in enumerate(current_new_urls):
        title = ""
        snippet = ""
        
        # 获取对应的标题和摘要（如果有）
        if i < len(search_snippets):
            snippet_data = search_snippets[i]
            title = snippet_data.get("title", "")
            snippet = snippet_data.get("snippet", "")
        
        # 第一步：HEAD 请求快速检查 URL 是否可访问
        is_accessible, status_code = check_url_accessibility(url)
        
        if not is_accessible:
            # URL 不可访问（404/403/408等），直接跳过，不调用 LLM
            print(f"  [URL预检] {url} -> 状态码 {status_code}，跳过")
            validated_results.append({
                "url": url,
                "is_valid": False,
                "reason": f"HTTP 状态码 {status_code}，页面不可访问",
                "corrected_company": "",
                "corrected_url": ""
            })
            continue
        
        # 第二步：使用 LLM 验证 URL 是否为职位详情页
        result = validate_url_with_llm(url, title, snippet)
        
        validated_results.append({
            "url": url,
            "is_valid": result.is_valid_job_detail_page,
            "reason": result.reason,
            "corrected_company": result.corrected_company,
            "corrected_url": result.corrected_url
        })
        
        if result.is_valid_job_detail_page:
            # 如果 URL 有效，直接使用
            valid_urls.append(url)
        elif result.corrected_url:
            # 如果提供了更正后的 URL，使用更正后的
            valid_urls.append(result.corrected_url)
    
    print(f"  [URL验证] 共 {len(current_new_urls)} 个URL，有效职位详情页: {len(valid_urls)} 个")
    
    return {
        "validated_urls": valid_urls,
        "url_validation_results": validated_results,
        "visited_urls": [],  # 不添加到 visited，避免重复
    }
