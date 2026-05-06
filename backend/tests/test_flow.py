"""
End-to-end flow tests for MindPilot.
Requires: docker compose up -d
Tests the complete pipeline: register → login → KB → document → chat
"""
import os
import socket
import tempfile
import time

import httpx
import pytest

BASE_URL = os.environ.get("MINDPILOT_URL", "http://localhost:8000")

# Fast TCP check (not HTTP, avoids timeout issues)
_BACKEND_OK = False
try:
    _host = os.environ.get("MINDPILOT_HOST", "localhost")
    s = socket.create_connection((_host, 8000), timeout=0.5)
    s.close()
    _BACKEND_OK = True
except Exception:
    pass

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _BACKEND_OK, reason="Backend not reachable on port 8000"),
]


class TestHealthEndpoints:
    """System health and metadata endpoints."""

    def test_health_returns_ok(self):
        resp = httpx.get(f"{BASE_URL}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_root_returns_welcome(self):
        resp = httpx.get(f"{BASE_URL}/", timeout=10)
        assert resp.status_code == 200
        assert "MindPilot" in resp.json()["message"]

    def test_openapi_schema(self):
        resp = httpx.get(f"{BASE_URL}/openapi.json", timeout=10)
        assert resp.status_code == 200
        schema = resp.json()
        assert len(schema["paths"]) >= 10


class TestAuthFlow:
    """Complete authentication flow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.username = f"flowtest_{int(time.time())}"
        self.password = "testpass123"
        self.token = None

    def test_01_register_new_user(self):
        resp = httpx.post(f"{BASE_URL}/api/auth/register", json={
            "username": self.username,
            "password": self.password,
        }, timeout=30)
        assert resp.status_code == 200, f"Register failed: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        assert data["username"] == self.username
        self.token = data["access_token"]

    def test_02_login_with_credentials(self):
        resp = httpx.post(f"{BASE_URL}/api/auth/login", json={
            "username": self.username,
            "password": self.password,
        }, timeout=30)
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        self.token = data["access_token"]

    def test_03_get_current_user(self):
        resp = httpx.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )
        assert resp.status_code == 200

    def test_04_protected_route_requires_auth(self):
        resp = httpx.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert resp.status_code in (401, 403)


class TestKnowledgeBaseFlow:
    """Knowledge base CRUD operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.username = f"kbflow_{int(time.time())}"
        self.kb_id = None
        # Register and get token
        resp = httpx.post(f"{BASE_URL}/api/auth/register", json={
            "username": self.username,
            "password": "testpass123",
        }, timeout=30)
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
        else:
            resp = httpx.post(f"{BASE_URL}/api/auth/login", json={
                "username": self.username,
                "password": "testpass123",
            }, timeout=30)
            self.token = resp.json()["access_token"]

    def test_01_create_knowledge_base(self):
        resp = httpx.post(f"{BASE_URL}/api/knowledge/", json={
            "name": f"Test KB {int(time.time())}",
            "description": "Integration test knowledge base",
        }, headers={"Authorization": f"Bearer {self.token}"}, timeout=30)
        assert resp.status_code == 200, f"Create KB failed: {resp.text}"
        data = resp.json()
        assert "id" in data
        self.kb_id = data["id"]

    def test_02_list_knowledge_bases(self):
        resp = httpx.get(
            f"{BASE_URL}/api/knowledge/",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "knowledges" in data

    def test_03_get_retrieval_config(self):
        resp = httpx.get(
            f"{BASE_URL}/api/knowledge/retrieval-config/config",
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "vector_weight" in data

    def test_04_update_retrieval_config(self):
        resp = httpx.put(
            f"{BASE_URL}/api/knowledge/retrieval-config/config",
            json={"vector_weight": 0.8, "bm25_weight": 0.2},
            timeout=30,
        )
        assert resp.status_code == 200


class TestChatFlow:
    """Chat and RAG pipeline."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.username = f"chatflow_{int(time.time())}"

    def test_general_chat(self):
        resp = httpx.post(f"{BASE_URL}/api/chat/", json={
            "query": "Hello, how are you?",
        }, timeout=60)
        assert resp.status_code == 200, f"Chat failed: {resp.text}"
        data = resp.json()
        assert "answer" in data

    def test_calculation_chat(self):
        resp = httpx.post(f"{BASE_URL}/api/chat/", json={
            "query": "What is 25 * 4?",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "100" in data["answer"]

    def test_session_consistency(self):
        session_id = f"test-session-{int(time.time())}"
        resp = httpx.post(f"{BASE_URL}/api/chat/", json={
            "query": "Hi",
            "session_id": session_id,
        }, timeout=60)
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id


class TestSSEStreaming:
    """SSE streaming endpoints."""

    def test_sse_stream_basic(self):
        with httpx.stream("POST", f"{BASE_URL}/api/chat/stream", json={
            "query": "Tell me a short joke",
        }, timeout=60) as resp:
            assert resp.status_code == 200
            events = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = httpx.json.loads(line[6:])
                    events.append(data.get("type"))
            assert "connected" in events
            assert "done" in events


class TestDocumentUpload:
    """Document upload and processing."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.username = f"docflow_{int(time.time())}"
        resp = httpx.post(f"{BASE_URL}/api/auth/register", json={
            "username": self.username,
            "password": "testpass123",
        }, timeout=30)
        if resp.status_code != 200:
            resp = httpx.post(f"{BASE_URL}/api/auth/login", json={
                "username": self.username,
                "password": "testpass123",
            }, timeout=30)
        self.token = resp.json()["access_token"]
        # Create a KB
        resp = httpx.post(f"{BASE_URL}/api/knowledge/", json={
            "name": f"DocTest KB {int(time.time())}",
            "description": "Document upload test",
        }, headers={"Authorization": f"Bearer {self.token}"}, timeout=30)
        self.kb_id = resp.json()["id"] if resp.status_code == 200 else None

    def test_upload_text_file(self):
        if not self.kb_id:
            pytest.skip("KB creation failed")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("MindPilot is an intelligent knowledge retrieval platform. " * 20)
            f.flush()
            f.close()

            with open(f.name, "rb") as fh:
                resp = httpx.post(
                    f"{BASE_URL}/api/document/upload",
                    data={"knowledge_id": self.kb_id},
                    files={"file": ("test_doc.txt", fh, "text/plain")},
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=60,
                )
            os.unlink(f.name)

            assert resp.status_code == 200, f"Upload failed: {resp.text}"
            data = resp.json()
            assert data["status"] == "processing"
            assert "doc_id" in data


class TestWorkflowEndpoints:
    """Workflow graph endpoints."""

    def test_get_workflow_graph(self):
        resp = httpx.get(f"{BASE_URL}/api/workflow/", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data

    def test_list_workflow_nodes(self):
        resp = httpx.get(f"{BASE_URL}/api/workflow/nodes", timeout=30)
        assert resp.status_code == 200

    def test_run_workflow(self):
        resp = httpx.post(f"{BASE_URL}/api/workflow/run", json={
            "query": "What is 50 + 50?",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
