-- MindPilot database initialization

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    avatar VARCHAR(255),
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    user_id VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(20),
    file_size BIGINT,
    knowledge_id VARCHAR(36),
    status VARCHAR(20) DEFAULT 'pending',
    chunk_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_knowledge_id (knowledge_id),
    INDEX idx_status (status)
);

CREATE TABLE IF NOT EXISTS chunks (
    id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(36),
    knowledge_id VARCHAR(36),
    chunk_index INT,
    content LONGTEXT,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_doc_id (doc_id),
    INDEX idx_knowledge_id (knowledge_id),
    FULLTEXT INDEX idx_content_ft (content) WITH PARSER ngram
);

CREATE TABLE IF NOT EXISTS retrieval_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    knowledge_id VARCHAR(36),
    vector_weight FLOAT DEFAULT 0.7,
    bm25_weight FLOAT DEFAULT 0.3,
    top_k INT DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_knowledge_id (knowledge_id)
);
