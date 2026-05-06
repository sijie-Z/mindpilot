# MindPilot - 多模态智能知识检索与多端协作平台

## 项目概述

**MindPilot** 是一款基于 RAG + 多Agent 协作的智能知识检索系统，支持文档、图片、截图的多模态理解，无缝接入网页 / QQ / 飞书等多端。

### 核心能力
- 多格式文档解析：PDF / Word / PPT，支持扫描件 OCR
- 多模态理解：图片问答、截图解析、架构图分析
- 精准检索：语义 + 关键词混合检索，自动重排序
- 多Agent协作：意图识别 → 检索 → 生成 → 评估，全链路编排
- 多端接入：网页对话 + QQ机器人 + 飞书机器人

---

## 一、技术架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户交互层                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│   │   Vue 3 前端    │  │   QQ 机器人    │  │   飞书机器人    │              │
│   │                 │  │   (NoneBot2)   │  │   (WebHook)     │              │
│   │  流式对话       │  │                 │  │                 │              │
│   │  图片上传       │  │  群聊@使用     │  │  企业内部使用    │              │
│   │  文档管理       │  │  私聊对话      │  │                 │              │
│   │  权重调节       │  │                 │  │                 │              │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
└─────────────────────────────── 共用后端 ─────────────────────────────────────┘
                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI 后端                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      LangGraph 多Agent编排                             │ │
│  │                                                                        │ │
│  │   ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐                │ │
│  │   │ Intent │───▶│Retrieval│───▶│ Answer │───▶│  Eval  │                │ │
│  │   │ (意图) │    │+Rerank │    │ (流式  │    │ (RAGAS │                │ │
│  │   │        │    │        │    │ 生成)  │    │ 评估)  │                │ │
│  │   └────────┘    └────────┘    └────────┘    └────────┘                │ │
│  │                                                                        │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │   │   SSE状态回传：「正在理解问题」「正在扩展搜索」...                │ │ │
│  │   └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                        │ │
│  │   Skill系统：搜索Skill │ RAGSkill │ 计算Skill │ 图片Skill │ MCP工具   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        RAG Pipeline                                    │ │
│  │                                                                        │ │
│  │   文档上传 ──▶ 解析（文字/OCR）──▶ 切片 ──▶ 向量化（智谱）           │ │
│  │                            │                                           │ │
│  │                      文本存MySQL                                        │ │
│  │                      向量存Milvus                                       │ │
│  │                            │                                           │ │
│  │   查询 ──▶ Query Expansion ──▶ 混合检索（权重可调）                    │ │
│  │                            │                                           │ │
│  │                      Rerank（从MySQL取内容）                           │ │
│  │                            │                                           │ │
│  │                      Self-RAG校验                                      │ │
│  │                            │                                           │ │
│  │                      流式生成 + 状态回传                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        多模态处理                                      │ │
│  │                                                                        │ │
│  │   ┌────────────┐  ┌────────────┐  ┌────────────┐                       │ │
│  │   │ PaddleOCR  │  │ GLM-4V     │  │ 图片描述   │                       │ │
│  │   │ (扫描件转文字)│  │ (看图回答) │  │ (VLM生成)  │                       │ │
│  │   └────────────┘  └────────────┘  └────────────┘                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        数据存储层                                     │ │
│  │                                                                        │ │
│  │   ┌──────────────────────────┐    ┌──────────────────────────┐       │ │
│  │   │        Milvus            │    │         MySQL             │       │ │
│  │   │   (仅存向量+ID)           │    │   (存完整文本+元数据)     │       │ │
│  │   │                          │    │   ngram全文索引          │       │ │
│  │   │  chunk_id | vector       │    │  id | content | metadata │       │ │
│  │   └──────────────────────────┘    └──────────────────────────┘       │ │
│  │                                     ↑                                  │ │
│  │                          Rerank时从MySQL取内容                         │ │
│  │                                                                        │ │
│  │   Redis: 会话状态 | 查询缓存 | Skill结果缓存                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        安全与部署                                      │ │
│  │                                                                        │ │
│  │   JWT + API Key 认证                                                    │ │
│  │   MySQL+Milvus 双写一致性（回滚机制）                                   │ │
│  │   Nginx proxy_buffering off（SSE优化）                                  │ │
│  │   Docker Compose 一键部署                                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、项目结构

```
mindpilot/
├── backend/                          # 后端项目
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI入口
│   │   ├── config.py                # 配置管理
│   │   │
│   │   ├── api/                     # API路由
│   │   │   ├── __init__.py
│   │   │   ├── chat.py              # 对话API（流式SSE）
│   │   │   ├── document.py          # 文档上传API
│   │   │   ├── knowledge.py         # 知识库管理API
│   │   │   ├── admin.py             # 管理后台API
│   │   │   └── image.py             # 图片处理API
│   │   │
│   │   ├── agents/                  # Agent模块
│   │   │   ├── __init__.py
│   │   │   ├── graph.py             # LangGraph状态机
│   │   │   ├── intent_agent.py      # 意图识别Agent
│   │   │   ├── retrieval_agent.py   # 检索Agent
│   │   │   ├── answer_agent.py      # 回答Agent
│   │   │   ├── eval_agent.py        # 评估Agent
│   │   │   └── state.py             # 状态定义
│   │   │
│   │   ├── skills/                  # Skill系统
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Skill基类
│   │   │   ├── search_skill.py      # 搜索Skill
│   │   │   ├── rag_skill.py         # RAG Skill
│   │   │   ├── calc_skill.py        # 计算Skill
│   │   │   ├── image_skill.py       # 图片理解Skill
│   │   │   └── registry.py          # Skill注册器
│   │   │
│   │   ├── rag/                     # RAG Pipeline
│   │   │   ├── __init__.py
│   │   │   ├── parser.py            # 文档解析器
│   │   │   ├── chunker.py           # 文本切片
│   │   │   ├── embedder.py          # 向量化（智谱）
│   │   │   ├── vector_store.py      # 向量存储（Milvus）
│   │   │   ├── retriever.py         # 检索器
│   │   │   ├── reranker.py          # 重排序
│   │   │   ├── evaluator.py         # RAGAS评估
│   │   │   └── consistency.py       # 数据一致性（双写回滚）
│   │   │
│   │   ├── multimodal/              # 多模态模块
│   │   │   ├── __init__.py
│   │   │   ├── ocr.py               # PaddleOCR
│   │   │   ├── vision.py            # GLM-4V 图片理解
│   │   │   └── image_describer.py    # 图片描述生成
│   │   │
│   │   ├── storage/                 # 存储模块
│   │   │   ├── __init__.py
│   │   │   ├── mysql.py             # MySQL连接
│   │   │   ├── redis_client.py      # Redis连接
│   │   │   └── models.py            # 数据模型
│   │   │
│   │   └── utils/                   # 工具模块
│   │       ├── __init__.py
│   │       ├── logger.py            # 日志
│   │       ├── auth.py              # JWT/API Key认证
│   │       └── mcp.py               # MCP协议实现
│   │
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                         # 前端项目
│   ├── src/
│   │   ├── api/                     # API调用
│   │   ├── components/             # 组件
│   │   ├── views/                   # 页面
│   │   ├── stores/                  # Pinia状态管理
│   │   └── router.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── bot/                              # QQ机器人
│   ├── bot.py                       # NoneBot2入口
│   ├── plugins/
│   │   ├── chat.py                 # 对话插件
│   │   └── admin.py                # 管理插件
│   └── pyproject.toml
│
├── nginx/
│   └── nginx.conf                   # Nginx配置（SSE优化）
│
├── docker-compose.yml               # 容器编排
├── .env.example                     # 环境变量模板
└── README.md                        # 项目说明
```

---

## 三、关键实现细节

### 3.1 MySQL + Milvus 数据一致性

```python
# backend/app/rag/consistency.py

class DataConsistencyManager:
    """
    MySQL + Milvus 双写一致性管理

    策略：先写MySQL，再写Milvus
    - 如果Milvus写入失败，回滚MySQL
    - 删除时采用双删策略
    """

    async def insert_chunks_with_rollback(
        self,
        chunks: list[dict],
        embeddings: list[list[float]]
    ) -> bool:
        """
        插入chunks，带回滚机制
        """
        chunk_ids = [c["id"] for c in chunks]

        try:
            # 1. 先写MySQL（文本+元数据）
            await self.mysql_repo.insert_chunks(chunks)

            # 2. 再写Milvus（向量）
            await self.milvus_repo.insert_vectors(chunk_ids, embeddings)

            return True

        except Exception as e:
            # 回滚：删除MySQL中的数据
            await self.mysql_repo.delete_chunks(chunk_ids)
            logger.error(f"数据一致性回滚: {e}")
            return False

    async def delete_document_with_rollback(self, doc_id: str):
        """
        删除文档，双删策略
        """
        # 1. 获取所有chunk_ids
        chunk_ids = await self.mysql_repo.get_chunk_ids_by_doc(doc_id)

        # 2. 删除MySQL
        await self.mysql_repo.delete_chunks(chunk_ids)

        # 3. 删除Milvus
        await self.milvus_repo.delete_vectors(chunk_ids)

        # 4. 删除文件
        await self.delete_file(doc_id)
```

**面试话术**：
> "MySQL和Milvus的数据一致性，我通过异常捕获+回滚机制解决。写入时先写MySQL再写Milvus，如果Milvus失败就回滚MySQL。删除时采用双删策略，确保两边数据一致。"

---

### 3.2 MySQL 全文搜索优化（ngram）

```sql
-- 创建表时配置 ngram 分词器

CREATE TABLE chunks (
    id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(36) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 普通索引
    INDEX idx_doc_id (doc_id),

    -- ngram 全文索引（支持中文分词）
    FULLTEXT INDEX content_fulltext (content) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 或者事后添加
ALTER TABLE chunks ADD FULLTEXT INDEX content_fulltext (content) WITH PARSER ngram;
```

```python
# backend/app/storage/mysql.py

class ChunkRepository:
    """Chunk数据访问层"""

    async def full_text_search(self, query: str, limit: int = 20) -> list[str]:
        """
        MySQL全文搜索（ngram分词）
        支持中文按词分词，而非按空格
        """
        async with self.session as session:
            # 使用 MATCH ... AGAINST 进行全文搜索
            stmt = select(Chunk.id).where(
                Chunk.content.match(query)  # MySQL FULLTEXT
            ).limit(limit)

            result = await session.execute(stmt)
            return [row[0] for row in result.all()]
```

**面试话术**：
> "MySQL自带的FULLTEXT对中文支持不好，默认按空格分词。我配置了ngram分词器，让它能正确地按中文词语分词，这样BM25检索中文时效果会好很多。"

---

### 3.3 SSE 流式响应优化

```python
# backend/app/api/chat.py

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话（带状态回传）"""

    async def event_generator():
        # ... 执行逻辑 ...

        # 1. 状态回传示例
        yield f"data: {json.dumps({'type': 'status', 'content': '正在理解您的问题...'})}\n\n"

        # 2. 意图识别
        intent = await agent.recognize_intent(request.query)
        yield f"data: {json.dumps({'type': 'intent', 'content': intent})}\n\n"

        # 3. 生成回答（逐chunk返回）
        async for chunk in agent.generate_stream(prompt):
            yield f"data: {json.dumps({'type': 'answer', 'content': chunk, 'chunk': True})}\n\n"

        # 4. 完成
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # 关键headers，防止代理缓存
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx关闭缓冲
        }
    )
```

**Nginx 配置（确保SSE不被缓存）**：

```nginx
# nginx/nginx.conf

server {
    listen 80;
    server_name localhost;

    # 关闭代理缓冲，确保SSE实时推送
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;

        # 关键配置
        proxy_buffering off;
        proxy_cache off;
        X-Accel-Buffering no;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 静态文件（前端）
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

**面试话术**：
> "SSE部署时有个坑：Nginx默认会缓存代理响应，导致前端收不到流。我在Nginx配置了proxy_buffering off和X-Accel-Buffering no，确保实时推送。前端也做了状态消息回传（'正在扩展搜索策略...'），让用户知道系统在运行，不是卡住了。"

---

### 3.4 多模态处理

```python
# backend/app/multimodal/ocr.py

class OCRProcessor:
    """PaddleOCR 扫描件识别"""

    async def extract_text_from_image(self, image_path: str) -> str:
        """从图片提取文字（用于建知识库）"""
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang='ch')
        result = ocr.ocr(image_path, cls=True)

        text = ""
        for line in result:
            for item in line:
                text += item[1][0] + "\n"

        return text

    async def extract_text_from_pdf(self, pdf_path: str) -> list[dict]:
        """从PDF提取文字和表格"""
        import pdfplumber

        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                # 提取文字
                text = page.extract_text() or ""

                # 提取表格
                tables = page.extract_tables()
                table_texts = []
                for table in tables:
                    table_str = "【表格】\n"
                    for row in table:
                        table_str += " | ".join(str(cell) for cell in row) + "\n"
                    table_texts.append(table_str)

                pages.append({
                    "page": i + 1,
                    "text": text,
                    "tables": table_texts
                })

        return pages
```

```python
# backend/app/multimodal/vision.py

class VisionProcessor:
    """GLM-4V 图片理解"""

    async def understand_image(self, image_path: str, query: str) -> str:
        """看图回答问题"""
        from zhipuai import ZhipuAI

        client = ZhipuAI(api_key=os.getenv("ZHIPU_API_KEY"))

        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        response = client.chat.completions.create(
            model="glm-4v-plus",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                    {"type": "text", "text": query}
                ]
            }]
        )

        return response.choices[0].message.content

    async def describe_image(self, image_path: str) -> str:
        """生成图片描述（用于建知识库）"""
        return await self.understand_image(
            image_path,
            "请详细描述这张图片的内容，包括文字、图表、结构等"
        )
```

---

## 四、开发优先级

| 阶段 | 优先级 | 功能 | 说明 |
|------|--------|------|------|
| **Phase 1** | P0 | FastAPI骨架 + 对话API | 核心入口 |
| | P0 | LangGraph单Agent | Agent能力 |
| | P0 | RAG基础（解析+切片） | 核心技术 |
| **Phase 2** | P1 | MySQL + Milvus 存储 | 数据持久化 |
| | P1 | 智谱Embedding | 向量化 |
| | P1 | 混合检索 + Rerank | 检索优化 |
| **Phase 3** | P1 | 多Agent协作 | 完整流程 |
| | P1 | SSE状态回传 | 用户体验 |
| | P1 | Vue前端 | 演示界面 |
| **Phase 4** | P2 | 数据一致性（回滚） | 工程细节 |
| | P2 | PaddleOCR + VLM | 多模态 |
| | P2 | QQ机器人 | 多端接入 |
| | P2 | Docker部署 | 收尾 |

---

## 五、环境变量

```bash
# 智谱API（主力）
ZHIPU_API_KEY=your-zhipu-api-key

# Claude（备选）
CLAUDE_API_KEY=your-claude-api-key

# 数据库
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=xxx
MYSQL_DATABASE=mindpilot

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=xxx

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 安全
SECRET_KEY=your-secret-key
API_KEY=your-api-key

# 可观测性（可选）
LANGFUSE_PUBLIC_KEY=xxx
LANGFUSE_SECRET_KEY=xxx
```

---

## 六、简历关键词

```
┌──────────────────────────────────────────────────────────────────────┐
│                         MindPilot 简历关键词                          │
├──────────────────────────────────────────────────────────────────────┤
│  多Agent编排    │ LangGraph状态机、意图识别、SSE状态回传              │
│  RAG全链路      │ 文档解析、切片、混合检索（权重可调）、Rerank、Self-RAG│
│  多模态处理     │ PaddleOCR、GLM-4V图片理解、VLM描述生成              │
│  数据一致性     │ MySQL+Milvus双写、回滚机制、双删策略                │
│  中文检索优化   │ ngram全文索引、BM25融合、RRF算法                   │
│  工程实践       │ FastAPI、Pydantic、JWT认证、Docker                 │
│  多端接入       │ Vue3网页、QQ机器人、飞书WebHook                    │
│  可观测性       │ LangFuse追踪、延迟监控、Token消耗                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

*项目版本：v1.0*
*更新时间：2026-04-25*