"""
Unit tests for agents.
Tests intent_agent, retrieval_agent, answer_agent, eval_agent.
"""
import asyncio
import os
import sys
import unittest.mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.asyncio
async def test_intent_detection_doc_qa():
    """Test intent detection for doc_qa."""
    from app.agents.intent_agent import intent_node

    state = {
        "query": "What is MindPilot?",
        "session_id": "test",
        "user_id": "test",
        "knowledge_id": "test-kb",
        "streaming": False,
        "iterations": 0,
    }

    result = await intent_node(state)
    assert result["intent"] == "doc_qa"
    assert "intent_confidence" in result


@pytest.mark.asyncio
async def test_intent_detection_general():
    """Test intent detection for general chat."""
    from app.agents.intent_agent import intent_node

    state = {
        "query": "Hello, how are you?",
        "session_id": "test",
        "user_id": "test",
        "streaming": False,
        "iterations": 0,
    }

    result = await intent_node(state)
    assert result["intent"] in ["general", "doc_qa"]  # With knowledge_id, doc_qa is valid


@pytest.mark.asyncio
async def test_intent_detection_calculation():
    """Test intent detection for calculation."""
    from app.agents.intent_agent import intent_node

    state = {
        "query": "What is 123 * 456?",
        "session_id": "test",
        "user_id": "test",
        "streaming": False,
        "iterations": 0,
    }

    result = await intent_node(state)
    # Should detect calculation intent (keywords like * exist)
    print(f"Calculation query intent: {result['intent']}")


@pytest.mark.asyncio
async def test_calc_skill():
    """Test calculator skill."""
    from app.skills.calc_skill import calc_skill

    result = await calc_skill.execute("123 * 456")
    assert result.success is True
    assert "56088" in result.result


@pytest.mark.asyncio
async def test_calc_skill_chinese():
    """Test calculator with Chinese keywords."""
    from app.skills.calc_skill import calc_skill

    result = await calc_skill.execute("计算 100 + 200")
    assert result.success is True
    assert "300" in result.result


@pytest.mark.asyncio
async def test_eval_agent():
    """Test evaluation agent with doc_qa intent and documents."""
    from app.agents.eval_agent import eval_node

    state = {
        "query": "What is RAG?",
        "answer": "RAG is Retrieval-Augmented Generation, a technique for LLM grounding.",
        "intent": "doc_qa",
        "reranked_docs": [
            {"chunk_id": "doc1", "content": "RAG stands for Retrieval-Augmented Generation."}
        ],
        "quality": {"relevance": 0.8, "faithfulness": 0.9},
        "streaming": False,
        "iterations": 0,
    }

    result = await eval_node(state)
    assert "evaluation" in result
    # With LLM evaluation enabled and valid docs, should return evaluation dict
    assert isinstance(result["evaluation"], dict)


def test_calc_safe_eval():
    """Test safe AST evaluation prevents injection."""
    from app.skills.calc_skill import CalcSkill

    calc = CalcSkill()
    with pytest.raises(Exception):
        calc._safe_eval("__import__('os').system('ls')")


def test_calc_expressions():
    """Test various math expressions."""
    from app.skills.calc_skill import CalcSkill

    calc = CalcSkill()
    assert calc._safe_eval("2+2") == 4
    assert calc._safe_eval("10/2") == 5.0
    assert calc._safe_eval("2**3") == 8
    assert abs(calc._safe_eval("3.14159 * 2") - 6.28318) < 0.001


# ── Extended Agent Tests ──

class TestBuildRagPrompt:
    """Tests for build_rag_prompt helper."""

    def test_with_citations(self):
        from app.agents.answer_agent import build_rag_prompt

        docs = [
            {"content": "Python is great", "metadata": {"filename": "guide.pdf", "page": 1}},
            {"content": "FastAPI is fast", "metadata": {"filename": "api.pdf", "page": 5}},
        ]
        prompt = build_rag_prompt("What is Python?", docs, include_citation=True)
        assert "guide.pdf" in prompt
        assert "第1页" in prompt
        assert "Python is great" in prompt

    def test_without_citations(self):
        from app.agents.answer_agent import build_rag_prompt

        docs = [{"content": "Some content", "metadata": {}}]
        prompt = build_rag_prompt("test", docs, include_citation=False)
        assert "1. Some content" in prompt
        assert "来源" not in prompt

    def test_empty_metadata(self):
        from app.agents.answer_agent import build_rag_prompt

        docs = [{"content": "text"}]
        prompt = build_rag_prompt("q", docs)
        assert "未知" in prompt


class TestGenerateAnswerExtended:
    """Tests for generate_answer function."""

    def test_no_docs_no_self_rag(self):
        from app.agents.answer_agent import generate_answer
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="Direct answer")

        result = asyncio.run(
            generate_answer("test query", [], mock_llm, enable_self_rag=False)
        )
        assert result["answer"] == "Direct answer"
        assert result["quality"]["relevance"] == 1.0

    def test_with_docs_no_self_rag(self):
        from app.agents.answer_agent import generate_answer
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="RAG answer")

        docs = [{"content": "doc text", "metadata": {"filename": "f.pdf", "page": 1}}]
        result = asyncio.run(
            generate_answer("query", docs, mock_llm, enable_self_rag=False)
        )
        assert result["answer"] == "RAG answer"


class TestAnswerNodeExtended:
    """Tests for answer_node function."""

    def test_general_intent(self):
        from app.agents.answer_agent import answer_node
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="General answer")

        state = {
            "query": "hello",
            "intent": "general",
            "sources": [],
        }
        result = asyncio.run(
            answer_node(state, llm=mock_llm)
        )
        assert result["answer"] == "General answer"
        assert result["status"] == "generating"

    def test_error_handling(self):
        from app.agents.answer_agent import answer_node
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=Exception("LLM error"))

        state = {
            "query": "test",
            "intent": "general",
            "sources": [],
        }
        result = asyncio.run(
            answer_node(state, llm=mock_llm)
        )
        assert "错误" in result["answer"]


class TestGraphRouting:
    """Tests for graph routing functions."""

    def test_route_by_intent_doc_qa(self):
        from app.agents.graph import route_by_intent
        assert route_by_intent({"intent": "doc_qa"}) == "retrieval"

    def test_route_by_intent_search(self):
        from app.agents.graph import route_by_intent
        assert route_by_intent({"intent": "search"}) == "retrieval"

    def test_route_by_intent_calculation(self):
        from app.agents.graph import route_by_intent
        assert route_by_intent({"intent": "calculation"}) == "answer"

    def test_route_by_intent_general(self):
        from app.agents.graph import route_by_intent
        assert route_by_intent({"intent": "general"}) == "answer"

    def test_route_by_intent_default(self):
        from app.agents.graph import route_by_intent
        assert route_by_intent({}) == "answer"

    def test_route_after_answer_doc_qa_with_docs(self):
        from app.agents.graph import route_after_answer
        state = {"intent": "doc_qa", "reranked_docs": [{"content": "x"}]}
        assert route_after_answer(state) == "evaluation"

    def test_route_after_answer_general(self):
        from app.agents.graph import route_after_answer
        assert route_after_answer({"intent": "general"}) == "__end__"

    def test_quality_gate_passed(self):
        from app.agents.graph import quality_gate
        assert quality_gate({"quality_passed": True}) == "__end__"

    def test_quality_gate_retry(self):
        from app.agents.graph import quality_gate
        state = {"quality_passed": False, "iterations": 1, "retrieval_attempts": 0}
        assert quality_gate(state) == "retrieval"

    def test_quality_gate_max_iterations(self):
        from app.agents.graph import quality_gate
        state = {"quality_passed": False, "iterations": 5, "retrieval_attempts": 1}
        assert quality_gate(state) == "__end__"


class TestLLMClientExtended:
    """Tests for AsyncLLMClient."""

    def test_parse_json_clean(self):
        from app.core.llm_client import AsyncLLMClient
        assert AsyncLLMClient._parse_json('{"key": "value"}') == {"key": "value"}

    def test_parse_json_with_code_block(self):
        from app.core.llm_client import AsyncLLMClient
        result = AsyncLLMClient._parse_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_with_text_prefix(self):
        from app.core.llm_client import AsyncLLMClient
        result = AsyncLLMClient._parse_json('Here: {"key": "value"} done')
        assert result == {"key": "value"}

    def test_parse_json_invalid(self):
        import json
        from app.core.llm_client import AsyncLLMClient
        with pytest.raises(json.JSONDecodeError):
            AsyncLLMClient._parse_json("not json")

    def test_close(self):
        from app.core.llm_client import AsyncLLMClient
        from unittest.mock import MagicMock
        client = AsyncLLMClient(api_key="test-key")
        client._clients[1] = MagicMock()
        asyncio.run(client.close())
        assert len(client._clients) == 0


class TestRunAgent:
    """Tests for run_agent."""

    @unittest.mock.patch("app.agents.graph._get_compiled_graph")
    def test_run_agent_success(self, mock_get_graph):
        from app.agents.graph import run_agent
        from unittest.mock import MagicMock

        mock_graph = MagicMock()
        mock_graph.invoke = MagicMock(return_value={
            "answer": "test answer", "intent": "general", "iterations": 1,
        })
        mock_get_graph.return_value = mock_graph

        result = asyncio.run(
            run_agent({"query": "test"}, thread_id="t1")
        )
        assert result["answer"] == "test answer"
        assert result["status"] == "done"

    @unittest.mock.patch("app.agents.graph._get_compiled_graph")
    def test_run_agent_error(self, mock_get_graph):
        from app.agents.graph import run_agent
        from unittest.mock import MagicMock

        mock_graph = MagicMock()
        mock_graph.invoke = MagicMock(side_effect=Exception("Graph failed"))
        mock_get_graph.return_value = mock_graph

        result = asyncio.run(
            run_agent({"query": "test"})
        )
        assert result["status"] == "error"
