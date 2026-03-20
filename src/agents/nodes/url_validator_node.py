# -*- coding: utf-8 -*-
"""
URL 验证器节点 - src/agents/nodes/url_validator_node.py

【本节点的核心使命】：省钱、提速、保纯度。
【工作流位置】：位于“搜索节点(搜回一堆网址)”之后，“爬虫节点(准备花大力气去抓取)”之前。
【业务痛点】：搜索引擎返回的 URL 经常是“公司首页”、“招聘列表页”甚至“死链（404）”。
如果直接让下游的无头浏览器去爬这些无效页面，不仅极度浪费运行时间，还会因为无效 HTML 太多导致 LLM Token 计费爆炸。
【解决方案（双重漏斗）】：
    第一重（物理探针）：发个极轻量的 HEAD 请求，戳一下网页，如果是 404，410 就直接扔掉。
    第二重（逻辑大脑）：让 LLM 看着搜索摘要，判断这到底是不是一个“职位详情页”。
"""

from typing import Dict, List
import httpx # 现代化的、支持异步的高性能 HTTP 客户端库
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field # 用于构建数据约束模型

from src.agents.state import AgentState
from src.config import get_llm_client, get_proxy
from src.utils.prompt_loader import load_prompt


# ==========================================
# 模块 1：定义大模型输出的结构图纸 (Schema)
# ==========================================
class URLValidationResult(BaseModel):
    """
    URL 验证结果。
    通过 Pydantic 配合 with_structured_output，我们强迫大模型不要说废话，
    必须乖乖地交出包含这 4 个字段的 JSON 表格。
    """
    # 核心判断开关：True 代表这是好链接，False 代表是垃圾链接
    is_valid_job_detail_page: bool = Field(description="是否为有效的职位详情页")
    
    # 强制大模型给出理由，防止它“幻觉瞎猜”，同时也方便我们后期看日志 Debug
    reason: str = Field(description="判断理由")
    
    # 【高级设计】：大模型在读摘要时，顺手把公司名字提出来
    corrected_company: str = Field(description="如果能找到，更正后的公司名称")
    
    # 【高阶容错】：有时候搜索到的 URL 带有乱七八糟的追踪后缀（如 ?source=baidu）
    # 如果大模型能认出来，它会在这里提供一个干净的 URL 替换掉原来的
    corrected_url: str = Field(description="如果原URL不是详情页，提供更准确的职位详情页URL（如有）")


# ==========================================
# 模块 2：第一重防线 - 物理轻量预检
# ==========================================
def check_url_accessibility(url: str, timeout: float = 5.0) -> tuple[bool, int | None]:
    """
    使用 HEAD 请求快速检查 URL 是否存活。
    【为什么用 HEAD 而不用 GET？】
    GET 会把整个网页的 HTML 代码、图片全都下载下来，很慢。
    HEAD 就像是去敲敲门，只问服务器：“这个网页在不在？”，服务器只返回状态码，不返回网页正文。
    """
    proxy = get_proxy() # 获取你在本地配置的代理（如果有的话）
    try:
        # 设置 timeout=5.0 秒，如果 5 秒敲门都没人理，直接放弃，不浪费时间
        with httpx.Client(proxy=proxy, timeout=timeout, follow_redirects=True) as client:
            response = client.head(url, headers={
                # 伪装成正常的 Windows Chrome 浏览器，防止被直接识别为低级爬虫
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            status_code = response.status_code
            
            # 【高危 Bug 已修复：反反爬误杀防线】
            # 很多招聘网站的安全策略很严，看到你发 HEAD 请求，会直接给你返回 403（禁止访问）或 405（方法不允许）。
            # 以前的代码写的是：只要不是 200~399 就判定死亡，这会误杀大量好链接！
            # 现在的逻辑（疑罪从无）：只坚决干掉 404（不存在）和 410（永久删除），其他的通通放行！
            if status_code in (404, 410):
                return False, status_code
            
            return True, status_code
            
    except httpx.TimeoutException:
        # 敲门超时（通常是对方服务器挂了，或者代理网络极差）
        return False, 408
    except httpx.RequestError:
        # 根本连不上（比如 URL 写错了，或者 DNS 解析不了）
        return False, None
    except Exception:
        # 兜底其他未知网络错误
        return False, None


# ==========================================
# 模块 3：提示词加载与兜底
# ==========================================
def _get_validator_prompt() -> str:
    """获取 URL 验证器的人设提示词"""
    try:
        return load_prompt("url_validator_system")
    except Exception:
        # 【修复】：加上了 Fallback，防止 markdown 文件丢失导致程序直接崩溃
        return """你是一个专业的 URL 过滤器。根据提供的 URL、标题和摘要，判断该页面是否为【具体的职位详情页】。
请剔除：公司首页、职位列表页、论坛讨论帖、新闻文章。
严格按 JSON 格式输出结果。"""


# ==========================================
# 模块 4：第二重防线 - LLM 语义大脑预检
# ==========================================
def validate_url_with_llm(url: str, title: str = "", snippet: str = "") -> URLValidationResult:
    """
    让大模型做阅读理解：看标题和摘要，判断页面属性。
    """
    llm = get_llm_client()
    
    # 给 LLM 施加 Pydantic 魔法，限制它只能返回 URLValidationResult 规定的字段
    structured_llm = llm.with_structured_output(URLValidationResult)
    
    system_prompt = _get_validator_prompt()
    
    # 把搜索工具找回来的数据，填进模板里交卷
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
        # 发送给 OpenAI / 本地大模型进行推理
        result: URLValidationResult = structured_llm.invoke(messages)
        return result
    except Exception as e:
        # 【防御性编程】：如果大模型 API 突然断开或者返回了乱码
        print(f"  [URL验证异常] {url}: {e}")
        # 返回一个“假”的判定结果，强行判定这个 URL 不合格，丢弃处理（宁缺毋滥）
        return URLValidationResult(
            is_valid_job_detail_page=False,
            reason=f"验证失败: {str(e)}",
            corrected_company="",
            corrected_url=""
        )


# ==========================================
# 模块 5：LangGraph 节点主业务控制流
# ==========================================
def url_validator_node(state: AgentState) -> Dict:
    """
    URL 验证节点主函数。
    接收上一节点（job_searcher）传来的批量 URL，通过双重漏斗过滤后，传给下一个节点。
    """
    # 1. 从状态账本中取出刚刚搜回来的新 URL 列表和对应的摘要
    current_new_urls = state.get("current_new_urls", [])
    search_snippets = state.get("current_search_snippets", [])
    
    # 如果搜索没找到任何东西，直接下班
    if not current_new_urls:
        return {
            "validated_urls": [],
            "url_validation_results": []
        }
    
    validated_results = [] # 记录每一个 URL 的宣判结果（用于写日志/Debug）
    valid_urls = []        # 存放最终幸存下来的纯净 URL（交给爬虫）
    
    # 2. 开始流水线审核，遍历每一个 URL
    for i, url in enumerate(current_new_urls):
        title = ""
        snippet = ""
        
        # 安全读取对应的摘要信息（防止数组越界报错）
        if i < len(search_snippets):
            snippet_data = search_snippets[i]
            title = snippet_data.get("title", "")
            snippet = snippet_data.get("snippet", "")
        
        # --- 漏斗第一关：物理探针 ---
        is_accessible, status_code = check_url_accessibility(url)
        
        # 如果是 404 死链，直接打回，跳过后面昂贵的 LLM 验证
        if not is_accessible:
            print(f"  [URL预检] {url} -> 确认为死链 (状态码 {status_code})，丢弃。")
            validated_results.append({
                "url": url,
                "is_valid": False,
                "reason": f"HTTP 状态码 {status_code}，页面不可访问",
                "corrected_company": "",
                "corrected_url": ""
            })
            continue 
        
        # --- 漏斗第二关：LLM 语义验证 ---
        # 如果网页存活，交给大模型做阅读理解
        result = validate_url_with_llm(url, title, snippet)
        
        # 记录判决书
        validated_results.append({
            "url": url,
            "is_valid": result.is_valid_job_detail_page,
            "reason": result.reason,
            "corrected_company": result.corrected_company,
            "corrected_url": result.corrected_url
        })
        
        # --- 根据判决结果进行收录 ---
        if result.is_valid_job_detail_page:
            # 大模型说这是好链接，直接加入白名单
            valid_urls.append(url)
        elif result.corrected_url:
            # 大模型说原链接不好，但它修好了一个新链接，把新链接加入白名单
            valid_urls.append(result.corrected_url)
    
    # 打印本轮漏斗的过滤成绩单
    print(f"  [URL验证] 搜索发现 {len(current_new_urls)} 个URL，通过双重验证存活: {len(valid_urls)} 个")
    
    # 3. 将幸存者更新回全局状态账本
    return {
        # 这些 valid_urls 会被下游的 scraper_node 拿去真正爬取网页主体
        "validated_urls": valid_urls,
        "url_validation_results": validated_results,
    }