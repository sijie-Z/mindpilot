"""
Intent recognition agent — determines what the user wants and routes accordingly.
Uses keyword pre-filtering + optional LLM refinement for edge cases.
"""
from datetime import UTC, datetime

from app.agents.state import AgentState
from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)

# Intent definitions with routing hints
INTENTS = {
    "doc_qa": {
        "name": "文档问答",
        "description": "用户询问关于上传文档的内容",
        "keywords": ["是什么", "如何", "怎么做", "解释", "说明", "文档", "内容", "根据", "总结"],
        "needs_retrieval": True,
    },
    "search": {
        "name": "网络搜索",
        "description": "用户询问需要实时信息",
        "keywords": ["今天", "最新", "新闻", "搜索", "现在", "实时", "最近"],
        "needs_retrieval": False,
    },
    "calculation": {
        "name": "数学计算",
        "description": "用户需要进行数学计算",
        "keywords": ["计算", "等于", "加", "减", "乘", "除", "平方", "开方", "算"],
        "needs_retrieval": False,
    },
    "code": {
        "name": "代码执行",
        "description": "用户询问或要求编写代码",
        "keywords": ["代码", "函数", "python", "写", "编程", "代码片段", "bug", "debug"],
        "needs_retrieval": False,
    },
    "analysis": {
        "name": "数据分析",
        "description": "用户需要分析数据、计算统计指标",
        "keywords": ["分析", "统计", "均值", "平均", "csv", "json", "数据", "图表"],
        "needs_retrieval": False,
    },
    "general": {
        "name": "通用问答",
        "description": "一般性对话或闲聊",
        "keywords": [],
        "needs_retrieval": False,
    },
}


async def intent_node(state: AgentState, llm: AsyncLLMClient | None = None) -> AgentState:
    """
    Recognize user intent.

    Strategy:
    1. Keyword pre-filter (fast path, handles ~80% of cases)
    2. If knowledge_id is set, bias toward doc_qa
    3. LLM refinement only for ambiguous cases
    """
    if llm is None:
        llm = AsyncLLMClient()

    query = state["query"]
    knowledge_id = state.get("knowledge_id")

    # ── Fast path: keyword matching ──
    detected_intent = "general"
    max_matches = 0

    for intent_name, info in INTENTS.items():
        if intent_name == "general":
            continue
        matches = sum(1 for kw in info["keywords"] if kw in query)
        if matches > max_matches:
            max_matches = matches
            detected_intent = intent_name

    # ── Knowledge bias ──
    if knowledge_id and detected_intent == "general":
        detected_intent = "doc_qa"

    # ── LLM refinement only when ambiguous ──
    confidence = 0.8 if max_matches >= 2 else (0.6 if max_matches == 1 else 0.4)
    if max_matches < 2 and not knowledge_id:
        try:
            result = await llm.chat_json(
                messages=[{
                    "role": "user",
                    "content": (
                        f"判断用户意图，只返回JSON。\n"
                        f"用户问题：「{query}」\n"
                        f'选项：doc_qa(文档问答) / search(网络搜索) / calculation(计算) '
                        f'/ code(编程) / analysis(数据分析) / general(通用)\n'
                        f'格式：{{"intent": "...", "reason": "..."}}'
                    ),
                }],
                temperature=0.1,
            )
            if result.get("intent") in INTENTS:
                detected_intent = result["intent"]
                confidence = 0.75
                logger.debug("LLM refined intent", intent=detected_intent, reason=result.get("reason"))
        except Exception as e:
            logger.warning("Intent LLM refinement failed, using keyword result", error=str(e))

    logger.info("Intent recognized", intent=detected_intent, confidence=confidence)

    return {
        **state,
        "intent": detected_intent,
        "intent_confidence": confidence,
        "status": "thinking",
        "created_at": datetime.now(UTC),
        "iterations": state.get("iterations", 0) + 1,
        "retrieval_attempts": 0,
        "quality_passed": True,
        "quality_feedback": "",
        "expanded_queries": [],
        "retrieved_docs": [],
        "reranked_docs": [],
        "evaluation": {},
        "messages": state.get("messages", []),
    }
