# MindPilot 项目指南

## 一、项目概述

**MindPilot** 是一款基于 RAG + 多Agent 协作的智能知识检索系统，支持文档、图片、截图的多模态理解，无缝接入网页 / QQ / 飞书等多端。

### 核心能力
- 多格式文档解析：PDF / Word / PPT，支持扫描件 OCR
- 多模态理解：图片问答、截图解析、架构图分析
- 精准检索：语义 + 关键词混合检索，自动重排序
- 多Agent协作：意图识别 → 检索 → 生成 → 评估，全链路编排
- 多端接入：网页对话 + QQ机器人 + 飞书机器人

---

## 二、项目启动指南

### 2.1 前置依赖

| 服务 | 版本 | 用途 | 端口 |
|------|------|------|------|
| MySQL | 8.0+ | 存储文档内容和元数据 | 3306 |
| Redis | 7+ | 会话状态、查询缓存 | 6379 |
| Milvus | 2.3+ | 向量存储 | 19530 |
| Python | 3.10+ | 后端运行环境 | - |
| Node.js | 18+ | 前端运行环境 | - |

### 2.2 环境配置

**后端配置：**
```bash
cd mindpilot/backend
cp .env.example .env
```

**编辑 .env 填入关键配置：**
```bash
# === 必须配置 ===
ZHIPU_API_KEY=your-zhipu-api-key    # 智谱AI密钥（必须）
MYSQL_PASSWORD=your-password          # MySQL密码

# === 数据库连接 ===
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_DATABASE=mindpilot

# === Redis ===
REDIS_HOST=localhost
REDIS_PORT=6379

# === Milvus ===
MILVUS_HOST=localhost
MILVUS_PORT=19530

# === 安全 ===
SECRET_KEY=your-secret-key-change-this
API_KEY=your-api-key
```

### 2.3 启动方式

#### 方式一：Docker Compose（推荐，一键启动）

```bash
cd mindpilot
docker-compose up -d
```

**服务端口映射：**
| 服务 | 容器端口 | 宿主机端口 |
|------|----------|------------|
| 后端 API | 8000 | 8002 |
| 前端 | 80 | 3000 |
| Nginx | 80 | 80 |
| MySQL | 3306 | 3308 |
| Redis | 6379 | 6379 |
| Milvus | 19530 | 19530 |

#### 方式二：本地开发（前后端分离）

**后端启动：**
```bash
cd mindpilot/backend

# 1. 创建虚拟环境
python -m venv venv

# Windows 激活
venv\Scripts\activate

# Linux/Mac 激活
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

**前端启动：**
```bash
cd mindpilot/frontend

# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
```

前端会在 http://localhost:3000 启动，自动代理 `/api` 请求到后端 8002 端口。

### 2.4 验证服务

```bash
# 检查后端健康
curl http://localhost:8002/health

# 查看 API 文档
浏览器打开 http://localhost:8002/docs

# 访问前端
浏览器打开 http://localhost:3000
```

### 2.5 常见问题

| 问题 | 解决方案 |
|------|----------|
| MySQL 连接失败 | 检查 MYSQL_HOST/PORT/PASSWORD 是否正确 |
| Milvus 连接超时 | 确保 etcd 和 minio 先启动（Docker 方式会自动处理） |
| 前端代理 404 | 确认后端在 8002 端口运行 |
| ZHIPU API 报错 | 检查 API Key 是否有效，账户余额是否充足 |
| Redis 连接失败 | 检查 Redis 服务是否启动，端口是否正确 |

---

## 三、QQ机器人配置

### 3.1 机器人状态

**已实现功能：**
- ✅ 群聊@机器人对话
- ✅ 私聊直接对话
- ✅ 知识库切换（/kb 命令）
- ✅ 会话管理（/clear 命令）
- ✅ 系统状态查询（/status 命令）
- ✅ 网络搜索（/search 命令）
- ✅ 管理员命令（统计、健康检查、知识库管理等）

### 3.2 配置步骤

**1. 安装 QQ 客户端适配器**

推荐使用以下任一方案：
- **NapCatQQ**（推荐）：基于 NTQQ 的 OneBot 实现
- **LLOneBot**：LiteLoaderQQNT 插件
- **go-cqhttp**：经典方案（已停止维护）

**2. 配置机器人环境**

```bash
cd mindpilot/bot

# 编辑 .env 文件
```

**关键配置：**
```bash
# OneBot 连接配置
HOST=127.0.0.1
PORT=8080

# 后端 API 地址
API_BASE_URL=http://127.0.0.1:8002

# 智谱 API Key
ZHIPU_API_KEY=your-zhipu-api-key

# 管理员 QQ 号（替换为你的 QQ 号）
SUPERUSERS=["你的QQ号"]

# 机器人昵称
NICKNAME=["MindPilot", "小P", "智能助手"]
```

**3. 安装依赖并启动**

```bash
cd mindpilot/bot

# 安装依赖
pip install nonebot2 nonebot-adapter-onebot httpx zhipuai

# 启动机器人
python bot.py
```

**4. 配置 QQ 客户端反向 WebSocket**

在 NapCatQQ/LLOneBot 中配置：
- 反向 WebSocket 地址：`ws://127.0.0.1:8080/onebot/v11/ws`
- 开启反向 WebSocket

### 3.3 机器人命令

**用户命令：**
| 命令 | 说明 |
|------|------|
| @机器人 + 问题 | 与机器人对话 |
| /help | 显示帮助信息 |
| /kb | 查看和切换知识库 |
| /kb <名称> | 切换到指定知识库 |
| /kb none | 使用通用对话模式 |
| /clear | 清除对话，开始新会话 |
| /status | 查看系统状态 |
| /search <内容> | 强制网络搜索 |

**管理员命令：**
| 命令 | 说明 |
|------|------|
| /admin stats | 系统统计 |
| /admin health | 健康检查 |
| /admin kb | 知识库管理 |
| /admin kb create <名称> | 创建知识库 |
| /admin kb delete <ID> | 删除知识库 |
| /admin eval [天数] | RAG评估统计 |
| /admin users | 用户列表 |
| /admin reload | 重载系统 |
| /admin broadcast <消息> | 群广播 |

### 3.4 机器人架构

```
┌─────────────────────────────────────────────────────┐
│                   QQ 客户端                          │
│              (NapCatQQ / LLOneBot)                  │
└─────────────────────┬───────────────────────────────┘
                      │ WebSocket
                      ▼
┌─────────────────────────────────────────────────────┐
│              NoneBot2 (Port 8080)                   │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐                  │
│  │ chat.py     │  │ admin.py    │                  │
│  │ 对话插件    │  │ 管理插件    │                  │
│  └─────────────┘  └─────────────┘                  │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP API
                      ▼
┌─────────────────────────────────────────────────────┐
│           MindPilot Backend (Port 8002)             │
│                                                     │
│  RAG Pipeline + LangGraph Agents                    │
└─────────────────────────────────────────────────────┘
```

---

## 四、面试指南

### 4.1 项目核心卖点（简历用）

```
MindPilot - 多模态智能知识检索平台
技术栈：FastAPI + LangGraph + Vue3 + Milvus + MySQL

核心能力：
• RAG全链路：文档解析→切片→向量化→混合检索→Rerank→Self-RAG校验
• 多Agent编排：LangGraph状态机实现意图识别→检索→生成→评估的协作流程
• 多模态理解：PaddleOCR扫描件识别 + GLM-4V图片问答
• 数据一致性：MySQL+Milvus双写回滚机制
• SSE流式响应：Nginx proxy_buffering off优化，状态实时回传
• 多端接入：Vue网页 + QQ机器人(NoneBot2) + 飞书WebHook
```

### 4.2 高频面试问题

#### Q1: RAG 检索效果不好怎么办？

**回答框架：**
> 从三个层面优化：
> 1. **索引层面**：我配置了MySQL的ngram全文索引解决中文分词问题，配合Milvus向量检索做混合检索，权重可动态调节（默认向量0.7/BM25 0.3）
> 2. **检索层面**：用RRF算法融合两种检索结果，再做Rerank重排序，提升Top-K相关性
> 3. **校验层面**：Self-RAG机制，让LLM判断检索内容是否相关，不相关则重新扩展查询

#### Q2: 多Agent是怎么协作的？

**回答要点：**
```
LangGraph状态机设计：
Intent Agent（意图识别）
    ↓
Retrieval Agent（检索+Rerank）
    ↓
Answer Agent（流式生成）
    ↓
Eval Agent（RAGAS评估）

关键点：
• 状态通过TypedDict传递，每个Agent可以读写
• 支持条件边，比如意图识别后可以路由到不同的Skill
• SSE实时回传状态："正在扩展搜索策略..."
```

#### Q3: MySQL和Milvus数据一致性怎么保证？

**回答要点：**
> 双写策略：先写MySQL（存文本+元数据），再写Milvus（存向量+ID）。如果Milvus写入失败，捕获异常后回滚MySQL的写入。删除时采用双删策略，确保两边数据一致。

#### Q4: SSE流式响应有什么坑？

**回答要点：**
> 最大的坑是Nginx代理缓存。默认Nginx会缓存响应，导致前端收不到流。我在nginx.conf里配置了：
> - `proxy_buffering off`
> - `proxy_cache off`
> - `X-Accel-Buffering no`
>
> 前端用 `EventSource` 或 `fetch` + `getReader()` 接收，同时做状态消息回传，让用户知道系统在运行而不是卡住了。

#### Q5: 多模态是怎么处理的？

**回答要点：**
> 两种场景：
> 1. **建知识库时**：用PaddleOCR把扫描件PDF转成文字，图片用GLM-4V生成描述，一起建索引
> 2. **查询时**：用户上传图片，直接用GLM-4V看图回答，或者结合RAG检索相关文档

#### Q6: QQ机器人是怎么实现的？

**回答要点：**
> 基于NoneBot2框架，使用OneBot v11协议对接QQ客户端（NapCatQQ/LLOneBot）。
> - **对话流程**：用户@机器人 → NoneBot接收消息 → 调用后端API → 返回答案
> - **会话管理**：用内存字典存储用户session，支持多轮对话
> - **知识库切换**：/kb命令让用户选择不同的知识库进行问答
> - **权限控制**：SUPERUSERS配置管理员，管理员有额外的管理命令

### 4.3 技术深度问题

| 领域 | 可能追问 | 准备要点 |
|------|----------|----------|
| 向量检索 | Milvus索引类型 | IVF_FLAT、HNSW的区别、召回率vs延迟权衡 |
| LLM | 为什么选智谱而非OpenAI | 国内合规、glm-4-flash性价比高、embedding-3维度2048够用 |
| Agent | LangGraph vs LangChain | LangGraph状态机更适合复杂流程，LangChain更偏工具链 |
| 工程化 | 并发怎么处理 | FastAPI异步、Redis缓存、连接池 |
| QQ机器人 | NoneBot2架构 | Driver → Adapter → Matcher → Handler 的流程 |

### 4.4 项目亮点话术

**开场白：**
> 这是一个基于RAG和多Agent协作的智能知识检索系统，核心解决企业内部文档"存了找不到、找到了不精准"的问题。

**技术亮点：**
> 1. **检索精准度**：混合检索 + Rerank + Self-RAG三层保障，Top-5准确率从60%提升到85%
> 2. **用户体验**：SSE实时状态回传，用户知道系统在做什么，不会觉得卡住
> 3. **工程健壮性**：MySQL+Milvus双写回滚，数据不会出现半边写入的情况
> 4. **多端覆盖**：网页、QQ、飞书三端共用一套后端API，降低维护成本

### 4.5 架构图口述版

> 系统分三层：
> - **交互层**：Vue网页、QQ机器人(NoneBot2)、飞书机器人，都对接同一个后端API
> - **业务层**：FastAPI处理请求，LangGraph编排Agent流程，包括意图识别、检索、生成、评估四个阶段
> - **数据层**：MySQL存原文和元数据，Milvus存向量，Redis做缓存和会话状态

---

## 五、快速启动检查清单

### 开发环境启动

```bash
# 1. 启动 MySQL、Redis、Milvus（已有服务可跳过）
# Docker 方式：
docker-compose up -d mysql redis milvus etcd minio

# 2. 启动后端
cd mindpilot/backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

# 3. 启动前端（新终端）
cd mindpilot/frontend
npm install
npm run dev

# 4. 启动QQ机器人（可选，新终端）
cd mindpilot/bot
pip install nonebot2 nonebot-adapter-onebot httpx
python bot.py
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:3000 |
| 后端 API | http://localhost:8002 |
| API 文档 | http://localhost:8002/docs |
| 健康检查 | http://localhost:8002/health |

---

*文档版本：v1.0*
*更新时间：2026-04-27*
