"""
Workflow engine for custom agent pipeline orchestration.

Supports:
- Custom node definitions
- Conditional branching
- Parallel execution
- Loop with max_iterations
- State sharing between nodes
"""
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel


class NodeType(str, Enum):
    """Types of workflow nodes."""
    AGENT = "agent"
    SKILL = "skill"
    CONDITION = "condition"
    PARALLEL = "parallel"
    TRANSFORM = "transform"
    INPUT = "input"
    OUTPUT = "output"


class NodeStatus(str, Enum):
    """Status of a node execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowNode:
    """A single node in the workflow."""
    id: str
    name: str
    node_type: NodeType
    handler: Callable | None = None
    config: dict[str, Any] = field(default_factory=dict)
    next_nodes: list[str] = field(default_factory=list)
    condition: Callable | None = None  # For conditional nodes

    # Runtime state
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: str | None = None
    latency_ms: int = 0


@dataclass
class WorkflowEdge:
    """An edge connecting two nodes."""
    source: str
    target: str
    condition: Callable | None = None  # Condition to traverse this edge


class WorkflowState(BaseModel):
    """Shared state across workflow nodes."""
    query: str
    session_id: str = ""
    user_id: str = ""
    knowledge_id: str | None = None
    current_node: str = ""
    iteration: int = 0
    max_iterations: int = 5

    # Results from each node
    node_results: dict[str, Any] = {}
    node_latencies: dict[str, int] = {}

    # Final output
    answer: str = ""
    sources: list[dict[str, Any]] = []
    evaluation: dict[str, float] = {}
    status: str = "pending"

    model_config = {"arbitrary_types_allowed": True}


class Workflow:
    """
    Workflow engine that orchestrates multiple nodes.

    Usage:
        wf = Workflow("my_workflow")
        wf.add_node("intent", NodeType.AGENT, handler=intent_handler)
        wf.add_node("retrieval", NodeType.AGENT, handler=retrieval_handler)
        wf.add_node("answer", NodeType.AGENT, handler=answer_handler)
        wf.add_edge("intent", "retrieval")
        wf.add_edge("retrieval", "answer")
        result = await wf.run(state)
    """

    def __init__(self, name: str, description: str = ""):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.nodes: dict[str, WorkflowNode] = {}
        self.edges: list[WorkflowEdge] = []
        self.entry_node: str | None = None

    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        handler: Callable | None = None,
        config: dict[str, Any] = None,
        name: str = "",
    ) -> "Workflow":
        """
        Add a node to the workflow.

        Args:
            node_id: Unique identifier
            node_type: Type of node
            handler: Async function to execute
            config: Node configuration
            name: Human-readable name

        Returns:
            self (for chaining)
        """
        node = WorkflowNode(
            id=node_id,
            name=name or node_id,
            node_type=node_type,
            handler=handler,
            config=config or {},
        )
        self.nodes[node_id] = node

        # First added node is entry point
        if not self.entry_node:
            self.entry_node = node_id

        return self

    def add_edge(
        self,
        source: str,
        target: str,
        condition: Callable | None = None,
    ) -> "Workflow":
        """
        Add an edge between two nodes.

        Args:
            source: Source node ID
            target: Target node ID
            condition: Optional condition function(state) -> bool

        Returns:
            self (for chaining)
        """
        if source not in self.nodes:
            raise ValueError(f"Source node not found: {source}")
        if target not in self.nodes:
            raise ValueError(f"Target node not found: {target}")

        edge = WorkflowEdge(source=source, target=target, condition=condition)
        self.edges.append(edge)
        self.nodes[source].next_nodes.append(target)

        return self

    def add_conditional_edge(
        self,
        source: str,
        branches: dict[str, Callable],
    ) -> "Workflow":
        """
        Add conditional edges from a node.

        Args:
            source: Source node ID
            branches: Dict mapping target_node_id -> condition_function

        Returns:
            self (for chaining)
        """
        for target, condition in branches.items():
            self.add_edge(source, target, condition)

        return self

    def get_next_nodes(self, node_id: str, state: WorkflowState) -> list[str]:
        """Get next nodes to execute based on conditions."""
        next_nodes = []

        for edge in self.edges:
            if edge.source == node_id:
                if edge.condition is None or edge.condition(state):
                    next_nodes.append(edge.target)

        return next_nodes

    async def run(self, state: WorkflowState) -> WorkflowState:
        """
        Execute the workflow.

        Args:
            state: Initial workflow state

        Returns:
            Updated state with results
        """
        if not self.entry_node:
            raise ValueError("No entry node defined")

        state.status = "running"
        current_nodes = [self.entry_node]
        visited: set[str] = set()

        while current_nodes and state.iteration < state.max_iterations:
            state.iteration += 1
            next_round = []

            for node_id in current_nodes:
                if node_id in visited and self.nodes[node_id].node_type != NodeType.CONDITION:
                    continue

                node = self.nodes[node_id]
                node.status = NodeStatus.RUNNING
                state.current_node = node_id

                start_time = time.time()

                try:
                    if node.handler:
                        result = await node.handler(state, node.config)
                        node.result = result
                        state.node_results[node_id] = result

                    node.status = NodeStatus.COMPLETED

                except Exception as e:
                    node.status = NodeStatus.FAILED
                    node.error = str(e)
                    state.status = "error"
                    return state

                node.latency_ms = int((time.time() - start_time) * 1000)
                state.node_latencies[node_id] = node.latency_ms

                # Get next nodes
                nexts = self.get_next_nodes(node_id, state)
                next_round.extend(nexts)
                visited.add(node_id)

            current_nodes = list(set(next_round))  # Deduplicate

        state.status = "done"
        return state

    def to_dict(self) -> dict[str, Any]:
        """Serialize workflow to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "type": n.node_type.value,
                    "config": n.config,
                    "next": n.next_nodes,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "has_condition": e.condition is not None}
                for e in self.edges
            ],
        }


def create_default_workflow() -> Workflow:
    """
    Create the default MindPilot workflow.

    Flow: Input -> Intent -> (conditional branch) -> Retrieval -> Rerank -> Answer -> Eval -> Output
    """
    from app.agents.answer_agent import answer_node
    from app.agents.eval_agent import eval_node
    from app.agents.intent_agent import intent_node
    from app.agents.retrieval_agent import retrieval_node

    wf = Workflow(
        name="mindpilot_default",
        description="Default MindPilot RAG workflow with multi-agent orchestration",
    )

    # Wrapper functions to adapt agent nodes to workflow handlers
    async def intent_handler(state: WorkflowState, config: dict) -> dict:
        agent_state = {
            "query": state.query,
            "session_id": state.session_id,
            "user_id": state.user_id,
            "knowledge_id": state.knowledge_id,
            "iterations": 0,
        }
        result = await intent_node(agent_state)
        return result

    async def retrieval_handler(state: WorkflowState, config: dict) -> dict:
        agent_state = state.node_results.get("intent", {})
        agent_state["query"] = state.query
        result = await retrieval_node(agent_state)
        return result

    async def answer_handler(state: WorkflowState, config: dict) -> dict:
        agent_state = state.node_results.get("retrieval", state.node_results.get("intent", {}))
        agent_state["query"] = state.query
        result = await answer_node(agent_state)
        return result

    async def eval_handler(state: WorkflowState, config: dict) -> dict:
        agent_state = state.node_results.get("answer", {})
        agent_state["query"] = state.query
        result = await eval_node(agent_state)
        state.answer = result.get("answer", "")
        state.sources = result.get("sources", [])
        state.evaluation = result.get("evaluation", {})
        return result

    # Add nodes
    wf.add_node("intent", NodeType.AGENT, handler=intent_handler, name="Intent Recognition")
    wf.add_node("retrieval", NodeType.AGENT, handler=retrieval_handler, name="Document Retrieval")
    wf.add_node("answer", NodeType.AGENT, handler=answer_handler, name="Answer Generation")
    wf.add_node("evaluation", NodeType.AGENT, handler=eval_handler, name="Quality Evaluation")

    # Add edges
    # Intent -> Retrieval (only for doc_qa)
    wf.add_conditional_edge("intent", {
        "retrieval": lambda s: s.node_results.get("intent", {}).get("intent") == "doc_qa",
        "answer": lambda s: s.node_results.get("intent", {}).get("intent") != "doc_qa",
    })

    wf.add_edge("retrieval", "answer")
    wf.add_edge("answer", "evaluation")

    return wf


# Global workflow instance
default_workflow = create_default_workflow()
