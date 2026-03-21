# -*- coding: utf-8 -*-
# 上面这行告诉 Python 解释器，这个文件使用的是 UTF-8 编码，这样写中文注释就不会乱码啦。

"""
配置文件 - src/config.py
该文件负责管理全局环境变量与工程参数配置，包括 LLM 客户端初始化、API 密钥加载等。
"""

import os  # 导入操作系统接口模块，用于读取环境变量
from typing import Optional  # 导入 Optional，用于标记某个变量可能为空（None）
from langchain_openai import ChatOpenAI  # 导入 LangChain 提供的 OpenAI 对话模型工具
from dotenv import load_dotenv  # 导入加载 .env 文件的工具

# 执行加载操作，它会去寻找项目根目录下的 .env 文件，把里面的变量存入系统环境变量中
load_dotenv()


def get_openai_api_key() -> str:
    """获取 OpenAI API 密钥"""
    # 尝试从环境变量中读取名为 OPENAI_API_KEY 的值
    api_key = os.getenv("OPENAI_API_KEY")
    # 如果没找到（变量为空）
    if not api_key:
        # 抛出一个错误，程序会在这里停下，大声告诉你：“去配置你的 .env 文件！”
        raise ValueError("未设置 OPENAI_API_KEY 环境变量，请在 .env 文件中配置")
    # 如果找到了，就把这把“钥匙”交出去
    return api_key


def get_tavily_api_key() -> str:
    """获取 Tavily API 密钥"""
    # 和上面同理，这次是去拿 Tavily（一个专为 AI 设计的搜索引擎）的钥匙
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("未设置 TAVILY_API_KEY 环境变量，请在 .env 文件中配置")
    return api_key


def get_proxy() -> Optional[str]:
    """获取代理地址，用于 LLM/Tavily 调用。"""
    # 依次检查系统里有没有配置 HTTP 或 HTTPS 代理（大小写都查一遍）
    # 如果在国内直连 OpenAI，通常需要配置这个。找到了就返回代理地址（如 http://127.0.0.1:7890），找不到就返回 None
    return os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("http_proxy") or os.getenv("https_proxy")


# 全局 LLM 客户端实例缓存
# 先定义一个全局变量 _llm_client，初始值是 None。
# 这样做的目的是：不管程序的其他地方调用多少次大模型，我们都只创建这一个实例，绝不多浪费内存。
_llm_client: Optional[ChatOpenAI] = None


def get_llm_client(
    model: str = "gpt-4o-mini",       # 默认使用的模型版本
    temperature: float = 0.5,         # 默认的发散度/创造力
    max_tokens: int = 2000,           # 默认的最大输出字数
    request_timeout: float = 30.0     # 默认的等待超时时间（30秒）
) -> ChatOpenAI:
    """获取 LLM 客户端实例"""
    global _llm_client  # 声明我们要使用的是外面那个全局变量 _llm_client

    # 【重要逻辑】：如果大脑已经被创建过了（不为 None），就直接把现成的大脑还回去，不再重复创建。
    if _llm_client is not None:
        return _llm_client

    # 局部导入包（只在需要用到的时候才导入，加快程序初始启动速度）
    import httpx
    from langchain_openai import ChatOpenAI

    # 调用前面的函数，拿到 OpenAI 的钥匙
    openai_key = get_openai_api_key()
    # 调用前面的函数，看看有没有配置网络代理
    proxy = get_proxy()

    # 准备一个字典，用来装一些额外的配置参数
    extra_kwargs = {
        "request_timeout": request_timeout,  # 设置超时时间
    }
    
    # 如果发现了网络代理
    if proxy:
        # 使用 httpx 创建一个带代理的网络客户端
        cust_http_client = httpx.Client(proxy=proxy)
        # 把这个配置好的客户端塞进我们的额外参数字典里
        extra_kwargs["http_client"] = cust_http_client

    # 【核心操作】：正式唤醒/初始化 ChatOpenAI 大脑！
    _llm_client = ChatOpenAI(
        model=model,                  # 指定大脑版本
        temperature=temperature,      # 指定性格（严肃还是跳脱）
        max_tokens=max_tokens,        # 指定话痨程度
        api_key=openai_key,           # 插入钥匙
        **extra_kwargs                # 把剩下的额外参数（比如超时时间、代理）全塞进去（** 语法是解包字典）
    )

    # 返回这颗新鲜出炉的“大脑”
    return _llm_client


class Config:
    """工程参数配置类"""
    # 这个类其实就是一个参数的“集装箱”，全大写是 Python 里的约定俗成，代表“常量”（不轻易改变的量）。
    
    TARGET_JOB_COUNT: int = 50          # 目标任务数量，比如 Agent 需要收集 50 个职位信息
    MAX_LOOP_COUNT: int = 30            # 最大循环次数，防止 Agent 陷入死循环疯掉
    MAX_SEARCH_RESULTS: int = 20        # 每次使用搜索引擎最多返回的结果条数
    CONTENT_TRUNCATION_LENGTH: int = 4000 # 文本截断长度，如果网页内容太长，只保留前 4000 个字符，防止大模型被撑爆
    SCRAPER_DELAY: float = 2.0          # 爬虫抓取延迟（每次抓完休息 2 秒），防止被目标网站封杀 IP
    RECURSION_LIMIT: int = 50          # 递归深度限制，同样是防止程序在复杂的任务中无限嵌套而崩溃


# 实例化为一个具体的对象 `config`，这样其他文件只需 `from config import config` 就能直接用这些参数了。
config = Config()