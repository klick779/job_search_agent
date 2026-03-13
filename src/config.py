# -*- coding: utf-8 -*-
"""
配置文件 - src/config.py
该文件负责管理全局环境变量与工程参数配置，包括 LLM 客户端初始化、API 密钥加载等。
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


def get_openai_api_key() -> str:
    """获取 OpenAI API 密钥"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("未设置 OPENAI_API_KEY 环境变量，请在 .env 文件中配置")
    return api_key


def get_tavily_api_key() -> str:
    """获取 Tavily API 密钥"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("未设置 TAVILY_API_KEY 环境变量，请在 .env 文件中配置")
    return api_key


def get_proxy() -> Optional[str]:
    """获取代理地址，用于 LLM/Tavily 调用。"""
    return os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("http_proxy") or os.getenv("https_proxy")


# 全局 LLM 客户端实例缓存
_llm_client: Optional[ChatOpenAI] = None


def get_llm_client(
    model: str = "gpt-4o-mini",
    temperature: float = 0.5,
    max_tokens: int = 2000,
    request_timeout: float = 30.0  # 默认 30 秒超时
) -> ChatOpenAI:
    """获取 LLM 客户端实例"""
    global _llm_client

    if _llm_client is not None:
        return _llm_client

    import httpx
    from langchain_openai import ChatOpenAI

    openai_key = get_openai_api_key()
    proxy = get_proxy()

    extra_kwargs = {
        "request_timeout": request_timeout,
    }
    # 使用 http_client 传入配置好的 httpx.Client（兼容新版本 httpx）
    if proxy:
        cust_http_client = httpx.Client(proxy=proxy)
        extra_kwargs["http_client"] = cust_http_client

    _llm_client = ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=openai_key,
        **extra_kwargs
    )

    return _llm_client


class Config:
    """工程参数配置类"""
    
    TARGET_JOB_COUNT: int = 50
    MAX_LOOP_COUNT: int = 30
    MAX_SEARCH_RESULTS: int = 20
    CONTENT_TRUNCATION_LENGTH: int = 4000
    SCRAPER_DELAY: float = 2.0
    RECURSION_LIMIT: int = 100


config = Config()
