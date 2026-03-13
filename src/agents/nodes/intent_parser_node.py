# -*- coding: utf-8 -*-
"""
意图解析节点
解析用户输入为结构化意图（目标岗位、数量、搜索关键词）
"""

from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.config import config, get_llm_client
from src.utils.prompt_loader import load_prompt


class ParsedIntent(BaseModel):
    """意图解析结果"""
    target_role: str = Field(description="用户想要搜索的目标岗位/角色名称")
    quantity: int = Field(description="用户希望获取的岗位条数", ge=1, le=100)
    search_keywords: list[str] = Field(description="根据目标岗位扩展的搜索关键词列表")


DEFAULT_QUANTITY = 20


def intent_parser_node(state: AgentState) -> Dict:
    """解析用户输入，提取目标岗位、数量和搜索关键词"""
    user_input = state.get("user_input", "")
    if not user_input:
        return {
            "target_role": "通用岗位",
            "target_count": config.TARGET_JOB_COUNT,
            "search_keywords": [],
        }

    intent = parse_user_intent(user_input)
    qty = intent.get("quantity", config.TARGET_JOB_COUNT)

    return {
        "target_role": intent.get("target_role", "通用岗位"),
        "target_count": qty,
        "search_keywords": intent.get("search_keywords", []),
    }


def parse_user_intent(user_message: str) -> Dict[str, Any]:
    """解析用户输入为结构化意图"""
    if not (user_message and user_message.strip()):
        return _default_intent()

    llm = get_llm_client()

    system_prompt = _get_intent_system_prompt()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"用户输入：\n{user_message.strip()}"),
    ]

    structured_llm = llm.with_structured_output(ParsedIntent)
    result: ParsedIntent = structured_llm.invoke(messages)

    role = (result.target_role or "").strip()
    qty = result.quantity or DEFAULT_QUANTITY
    qty = max(1, min(100, int(qty)))

    keywords = result.search_keywords[:5] if result.search_keywords else []

    return {
        "target_role": role,
        "quantity": qty,
        "search_keywords": [str(k).strip() for k in keywords if k],
    }


def _get_intent_system_prompt() -> str:
    try:
        return load_prompt("intent_parser_system")
    except Exception:
        return """从用户输入中提取 target_role（目标岗位）、quantity（数量）、search_keywords（搜索关键词）。
仅输出 JSON，字段名：target_role, quantity, search_keywords。"""


def _default_intent() -> Dict[str, Any]:
    return {
        "target_role": "",
        "quantity": DEFAULT_QUANTITY,
        "search_keywords": [],
    }
