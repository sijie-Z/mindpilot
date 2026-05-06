"""
LangGraph workflow with real conditional routing, quality feedback loops,
and checkpoint-based conversation memory.

Graph topology:
                        ┌──────────┐
                        │  intent  │
                        └────┬─────┘
                             │
                   ┌─────────┴──────────┐
                   │ route_by_intent    │
                   └─────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        doc_qa/search   calculation     general/other
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │retrieval │  │ skill    │  │ answer   │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             │              │              │
             ▼              │              │
        ┌──────────┐       │              │
        │ answer   │◄──────┘              │
        └────┬─────┘                      │
             │                            │
             ▼                            │
        ┌──────────┐                      │
        │   eval   │                      │
        └────┬─────┘                      │
             │                            │
     ┌───────┴───────┐                    │
     │ quality_gate  │                    │
     └───────┬───────┘                    │
             │                            │
    ┌────────┼────────┐                   │
    ▼        ▼        ▼                   │
  pass   retry(loop)  max                 │
    │        │        │                   │
    ▼        ▼        ▼                   │
   END   retrieval   END                  │
             └────────────────────────────┘
                       ▼
                      END
"""
import time

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.answer_agent import answer_node
from app.agents.eval_agent import eval_node
from app.agents.intent_agent import intent_node
from app.agents.retrieval_agent import retrieval_node
from app.agents.state import AgentState
from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)

# Quality threshold for triggering retrieval retry
QUALITY_RETRY_THRESHOLD = 0.5
MAX_RETRIEVAL_ATTEMPTS = 2
MAX_ITERATIONS = 5


# ── Routing functions ──

def route_by_intent(state: AgentState) -> str:
    """
    Conditional routing after intent detection.

    - doc_qa / search → retrieval (RAG pipeline)
    - calculation → answer (skill handles it internally)
    - code / general → answer (direct LLM)
    """
    intent = state.get("intent", "general")
    if intent in ("doc_qa", "search"):
        return "retrieval"
    return "answer"


def route_after_answer(state: AgentState) -> str:
    """
    After answer generation: run evaluation for doc_qa, skip for others.
    """
    intent = state.get("intent", "general")
    if intent == "doc_qa" and state.get("reranked_docs"):
        return "evaluation"
    return END


def quality_gate(state: AgentState) -> str:
    """
    Quality gate after evaluation.

    - Pass: END
    - Fail with retries remaining: loop back to retrieval
    - Fail with max retries: END (accept current answer)
    """
    quality_passed = state.get("quality_passed", True)
    if quality_passed:
        logger.info("Quality gate: passed")
        return END

    iterations = state.get("iterations", 1)
    retrieval_attempts = state.get("retrieval_attempts", 0)

    if iterations < MAX_ITERATIONS and retrieval_attempts < MAX_RETRIEVAL_ATTEMPTS:
        logger.info("Quality gate: retrying retrieval",
                    iterations=iterations, retrieval_attempts=retrieval_attempts)
        return "retrieval"

    logger.info("Quality gate: max attempts reached, accepting current answer")
    return END


# ── Graph construction ──

def create_agent_graph(checkpointer=None):
    """
    Build the agent workflow graph with conditional routing.
    Uses MemorySaver checkpointer for multi-turn conversation support.
    """
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("intent", _intent_wrapper)
    graph.add_node("retrieval", _retrieval_wrapper)
    graph.add_node("answer", _answer_wrapper)
    graph.add_node("evaluation", _eval_wrapper)

    # Entry
    graph.set_entry_point("intent")

    # Conditional edge from intent
    graph.add_conditional_edges(
        "intent",
        route_by_intent,
        {
            "retrieval": "retrieval",
            "answer": "answer",
        }
    )

    # Retrieval → Answer
    graph.add_edge("retrieval", "answer")

    # Answer → conditional (eval or END)
    graph.add_conditional_edges(
        "answer",
        route_after_answer,
        {
            "evaluation": "evaluation",
            END: END,
        }
    )

    # Evaluation → quality gate
    graph.add_conditional_edges(
        "evaluation",
        quality_gate,
        {
            "retrieval": "retrieval",
            END: END,
        }
    )

    if checkpointer is None:
        checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)


# ── Node wrappers (share a single LLM client instance) ──

_llm: AsyncLLMClient | None = None


def _get_llm() -> AsyncLLMClient:
    global _llm
    if _llm is None:
        _llm = AsyncLLMClient()
    return _llm


async def _intent_wrapper(state: AgentState) -> AgentState:
    return await intent_node(state, llm=_get_llm())


async def _retrieval_wrapper(state: AgentState) -> AgentState:
    return await retrieval_node(state, llm=_get_llm())


async def _answer_wrapper(state: AgentState) -> AgentState:
    return await answer_node(state, llm=_get_llm())


async def _eval_wrapper(state: AgentState) -> AgentState:
    return await eval_node(state, llm=_get_llm())


# ── Public API ──

async def run_agent(state: dict, thread_id: str = "default") -> dict:
    """
    Run the agent graph with protection and timing.

    Args:
        state: Initial state dict
        thread_id: Unique thread ID for checkpoint-based conversation memory

    Returns:
        Final state dict with answer, sources, evaluation
    """
    start = time.perf_counter()
    agent_graph = create_agent_graph()

    # Config with thread_id enables checkpoint/memory
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = agent_graph.invoke(state, config)
        latency_ms = int((time.perf_counter() - start) * 1000)
        result["latency_ms"] = latency_ms
        result["status"] = "done"
        logger.info("Agent run complete", latency_ms=latency_ms,
                    iterations=result.get("iterations", 1),
                    intent=result.get("intent", "unknown"))
        return result

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.error("Agent run failed", error=str(e), latency_ms=latency_ms)
        return {
            **state,
            "answer": f"抱歉，处理您的请求时发生了错误: {e}",
            "status": "error",
            "latency_ms": latency_ms,
            "iterations": state.get("iterations", 0),
        }


def run_agent_sync(state: dict, thread_id: str = "default") -> dict:
    """Synchronous wrapper for run_agent (used in tests or sync contexts)."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, run_agent(state, thread_id))
            return future.result()
    return asyncio.run(run_agent(state, thread_id))


# Pre-built graph for module-level import compatibility
agent_graph = create_agent_graph()
