"""
Integration tests for the full RAG pipeline and API endpoints.
Requires backend running on port 8002.
"""
import json
import os
import sys
import time

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.environ.get("MINDPILOT_URL", "http://127.0.0.1:8000")

_backend_live = False
try:
    resp = httpx.get(f"{BASE_URL}/health", timeout=3.0)
    _backend_live = resp.status_code == 200
except Exception:
    pass

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _backend_live, reason="Backend not running on port 8000"),
]


class TestHealthAPI:
    """Test basic system health."""

    def test_health(self):
        resp = httpx.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["app"] == "MindPilot"

    def test_root(self):
        resp = httpx.get(f"{BASE_URL}/")
        assert resp.status_code == 200

    def test_openapi(self):
        resp = httpx.get(f"{BASE_URL}/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        assert len(paths) >= 20  # At least 20 endpoints


class TestAuthAPI:
    """Test authentication endpoints."""

    def test_register_and_login(self):
        username = f"inttest_{int(time.time())}"
        with httpx.Client(base_url=BASE_URL, timeout=30) as c:
            # Register
            resp = c.post("/api/auth/register", json={
                "username": username,
                "password": "test123456",
            })
            assert resp.status_code == 200
            token = resp.json()["access_token"]
            assert len(token) > 50

            # Login
            resp = c.post("/api/auth/login", json={
                "username": username,
                "password": "test123456",
            })
            assert resp.status_code == 200
            assert "access_token" in resp.json()

    def test_duplicate_register(self):
        username = f"dup_test_{int(time.time())}"
        with httpx.Client(base_url=BASE_URL, timeout=30) as c:
            resp1 = c.post("/api/auth/register", json={
                "username": username, "password": "test123",
            })
            assert resp1.status_code == 200

            resp2 = c.post("/api/auth/register", json={
                "username": username, "password": "test123",
            })
            assert resp2.status_code == 400

    def test_invalid_login(self):
        resp = httpx.post(f"{BASE_URL}/api/auth/login", json={
            "username": "nonexistent_user_xyz",
            "password": "wrong",
        }, timeout=30)
        assert resp.status_code == 401

    def test_protected_endpoint(self):
        """Test /api/auth/me requires token."""
        resp = httpx.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert resp.status_code == 401 or resp.status_code == 403


class TestChatAPI:
    """Test chat endpoints."""

    def test_general_chat(self):
        resp = httpx.post(f"{BASE_URL}/api/chat/", json={
            "query": "What is 1+1?",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "session_id" in data
        assert "evaluation" in data

    def test_calculation_chat(self):
        resp = httpx.post(f"{BASE_URL}/api/chat/", json={
            "query": "calculate 99 * 99",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "9801" in data["answer"]

    def test_chat_session_id(self):
        """Test that session_id is returned and consistent."""
        resp = httpx.post(f"{BASE_URL}/api/chat/", json={
            "query": "Hello",
            "session_id": "test-session-123",
        }, timeout=60)
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "test-session-123"

    def test_sse_stream(self):
        """Test SSE streaming endpoint."""
        with httpx.stream("POST", f"{BASE_URL}/api/chat/stream", json={
            "query": "Hello",
        }, timeout=60) as resp:
            assert resp.status_code == 200

            events = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append(data["type"])

            assert "connected" in events
            assert "answer" in events
            assert "done" in events

    def test_sse_stream_rag(self):
        """Test SSE streaming with RAG pipeline."""
        with httpx.stream("POST", f"{BASE_URL}/api/chat/stream", json={
            "query": "What is MindPilot?",
            "knowledge_id": "6facc341-6281-4ecb-8a19-c8e0c9201446",
        }, timeout=60) as resp:
            assert resp.status_code == 200
            events = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append(data["type"])

            assert "connected" in events
            assert "intent" in events
            assert "done" in events


class TestKnowledgeAPI:
    """Test knowledge base management."""

    def test_create_knowledge(self):
        with httpx.Client(base_url=BASE_URL, timeout=30) as c:
            resp = c.post("/api/knowledge/", json={
                "name": f"test_kb_{int(time.time())}",
                "description": "Integration test KB",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "id" in data
            return data["id"]

    def test_list_knowledges(self):
        resp = httpx.get(f"{BASE_URL}/api/knowledge/", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "knowledges" in data
        assert isinstance(data["knowledges"], list)

    def test_get_retrieval_config(self):
        resp = httpx.get(f"{BASE_URL}/api/knowledge/retrieval-config/config", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "vector_weight" in data
        assert "bm25_weight" in data

    def test_update_retrieval_config(self):
        resp = httpx.put(f"{BASE_URL}/api/knowledge/retrieval-config/config", json={
            "vector_weight": 0.8,
            "bm25_weight": 0.2,
        }, timeout=30)
        assert resp.status_code == 200

    def test_system_stats(self):
        resp = httpx.get(f"{BASE_URL}/api/knowledge/stats/overview", timeout=30)
        assert resp.status_code == 200


class TestWorkflowAPI:
    """Test workflow endpoints."""

    def test_get_workflow(self):
        resp = httpx.get(f"{BASE_URL}/api/workflow/", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert len(data["nodes"]) >= 4  # intent, retrieval, answer, eval

    def test_list_nodes(self):
        resp = httpx.get(f"{BASE_URL}/api/workflow/nodes", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data

    def test_run_workflow(self):
        resp = httpx.post(f"{BASE_URL}/api/workflow/run", json={
            "query": "What is 2+2?",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "status" in data


class TestDocumentAPI:
    """Test document upload and management."""

    def test_upload_document(self, tmp_path):
        # Create a test file
        test_file = tmp_path / "test_upload.txt"
        test_file.write_text("This is a test document for MindPilot integration testing.")

        with httpx.Client(base_url=BASE_URL, timeout=60) as c:
            with open(test_file, "rb") as f:
                resp = c.post("/api/document/upload", data={
                    "knowledge_id": "6facc341-6281-4ecb-8a19-c8e0c9201446",
                }, files={"file": ("test_upload.txt", f, "text/plain")})

            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "processing"
            assert "doc_id" in data

    def test_list_documents(self):
        resp = httpx.get(f"{BASE_URL}/api/document/list", timeout=30)
        assert resp.status_code == 200

    def test_unsupported_file_type(self):
        resp = httpx.post(f"{BASE_URL}/api/document/upload", data={
            "knowledge_id": "test",
        }, files={"file": ("test.exe", b"binary", "application/octet-stream")}, timeout=30)
        assert resp.status_code == 400


class TestFeishuAPI:
    """Test Feishu bot endpoints."""

    def test_config(self):
        resp = httpx.get(f"{BASE_URL}/api/feishu/config", timeout=30)
        assert resp.status_code == 200

    def test_webhook_url_verification(self):
        resp = httpx.post(f"{BASE_URL}/api/feishu/webhook", json={
            "type": "url_verification",
            "challenge": "test_challenge_token",
            "token": "",
        }, timeout=30)
        # May fail if token mismatch, but endpoint should respond
        assert resp.status_code in [200, 401]
