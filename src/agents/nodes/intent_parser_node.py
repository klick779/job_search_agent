# -*- coding: utf-8 -*-
"""
意图解析节点 - src/agents/nodes/intent_parser_node.py
解析用户输入为结构化意图（目标岗位、数量、搜索关键词）
作用：消除自然语言的歧义，保护下游节点不被奇怪的输入搞崩溃。
"""

from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.config import config, get_llm_client
from src.utils.prompt_loader import load_prompt


# ---------- 核心数据图纸 (Schema) ----------
class ParsedIntent(BaseModel):
    """意图解析结果约束"""
    target_role: str = Field(description="用户想要搜索的目标岗位/角色名称")
    # 直接在 Prompt 层面告诉大模型数量限制
    quantity: int = Field(description="用户希望获取的岗位条数", ge=1, le=100)
    search_keywords: list[str] = Field(description="根据目标岗位扩展的搜索关键词列表")



def intent_parser_node(state: AgentState) -> Dict:
    """
    LangGraph 节点入口：解析用户输入，提取目标岗位、数量和搜索关键词
    """
    user_input = state.get("user_input", "")
    
    # 防御性拦截 1：如果用户没有任何输入
    if not user_input:
        return {
            "target_role": "通用岗位",
            "target_count": config.TARGET_JOB_COUNT, # 使用全局统一配置
            "search_keywords": [],
        }

    # 调用底层的 LLM 解析逻辑
    intent = parse_user_intent(user_input)
    
    qty = intent.get("quantity", config.TARGET_JOB_COUNT)

    # 返回给状态机，更新全局状态
    return {
        "target_role": intent.get("target_role") or "通用岗位",
        "target_count": qty,
        "search_keywords": intent.get("search_keywords") or ["实习", "校招", "应届生"],
    }


def parse_user_intent(user_message: str) -> Dict[str, Any]:
    """底层解析逻辑：调用大模型进行意图提取"""
    
    # 防御性拦截 2：防止全是空格的输入
    if not (user_message and user_message.strip()):
        return _default_intent()

    llm = get_llm_client()
    system_prompt = _get_intent_system_prompt()
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"用户输入：\n{user_message.strip()}"),
    ]

    # 给大模型施加 Pydantic 结构化输出的约束
    structured_llm = llm.with_structured_output(ParsedIntent)
    
    # 【高可用修复】：添加网络与接口异常捕获
    try:
        result: ParsedIntent = structured_llm.invoke(messages)
    except Exception as e:
        print(f"⚠️ 意图解析服务异常，退化为默认策略。错误详情: {e}")
        return _default_intent()

    # --- 双重防御与数据清洗区 ---
    
    # 1. 清洗角色名称
    role = (result.target_role or "").strip()
    
    # 2. 钳制数量：确保数量绝对在 [1, 100] 之间，防止撑爆内存
    qty = result.quantity or config.TARGET_JOB_COUNT
    qty = max(1, min(100, int(qty)))

    # 3. 截断关键词：最多只取前 5 个，防止大模型暴走
    keywords = result.search_keywords[:5] if result.search_keywords else []

    return {
        "target_role": role,
        "quantity": qty,
        # 4. 去除列表里每个词的空格并过滤空值
        "search_keywords": [str(k).strip() for k in keywords if k],
    }


def _get_intent_system_prompt() -> str:
    """加载提示词（带 Fallback 降级）"""
    try:
        return load_prompt("intent_parser_system")
    except Exception:
        # 内存级兜底提示词
        return """从用户输入中提取 target_role（目标岗位）、quantity（数量）、search_keywords（搜索关键词）。
仅输出 JSON，字段名：target_role, quantity, search_keywords。"""


def _default_intent() -> Dict[str, Any]:
    """生成兜底的默认意图数据（提供真正能跑通的默认值）"""
    return {
        "target_role": "AI工程师", 
        "quantity": config.TARGET_JOB_COUNT,
        "search_keywords": ["实习", "校招", "应届生"], 
    }