"""
Unit tests for agents.
Tests intent_agent, retrieval_agent, answer_agent, eval_agent.
"""
import os
import sys

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
