-- MindPilot Database Initialization
-- Schema matches SQLAlchemy models in app/storage/models.py

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    api_key VARCHAR(100) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Chat sessions
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    title VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Chat messages
CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at),
    FULLTEXT INDEX idx_content_ft (content) WITH PARSER ngram,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Knowledge bases
CREATE TABLE IF NOT EXISTS knowledges (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    user_id VARCHAR(36),
    is_public BOOLEAN DEFAULT FALSE,
    doc_count INT DEFAULT 0,
    chunk_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Documents
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY,
    knowledge_id VARCHAR(36) NOT NULL,
    filename VARCHAR(200) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(20),
    file_size INT,
    status ENUM('pending', 'processing', 'done', 'failed') DEFAULT 'pending',
    chunks INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_knowledge_id (knowledge_id),
    INDEX idx_status (status),
    FOREIGN KEY (knowledge_id) REFERENCES knowledges(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Document chunks for RAG
CREATE TABLE IF NOT EXISTS chunks (
    id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(36) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    metadata JSON,
    embedding_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_doc_id (doc_id),
    FULLTEXT INDEX idx_content_ft (content) WITH PARSER ngram,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- RAGAS evaluation records
CREATE TABLE IF NOT EXISTS evaluations (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36),
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    contexts JSON,
    metrics JSON,
    faithfulness FLOAT,
    answer_relevance FLOAT,
    context_precision FLOAT,
    context_recall FLOAT,
    latency_ms INT,
    tokens_used INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Retrieval configuration per knowledge base
CREATE TABLE IF NOT EXISTS retrieval_configs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    knowledge_id VARCHAR(36),
    vector_weight FLOAT DEFAULT 0.7,
    bm25_weight FLOAT DEFAULT 0.3,
    top_k INT DEFAULT 10,
    rerank_enabled BOOLEAN DEFAULT TRUE,
    self_rag_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_knowledge_id (knowledge_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Skill execution logs
CREATE TABLE IF NOT EXISTS skill_logs (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36),
    skill_name VARCHAR(50) NOT NULL,
    input_params JSON,
    output_result JSON,
    latency_ms INT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_skill_name (skill_name),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default retrieval config
INSERT IGNORE INTO retrieval_configs (id, vector_weight, bm25_weight, top_k, rerank_enabled, self_rag_enabled)
VALUES ('default-config', 0.7, 0.3, 10, TRUE, TRUE);
