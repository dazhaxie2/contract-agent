# Contract Agent - 合同合规智能体系统

基于 Agentic RAG 架构的合同合规审查平台，融合 Graph RAG、Self-RAG、CRAG 前沿技术，实现多库协同的智能合同分析、合规审查、条款比对与法律检索。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend (React + Ant Design)          │
│  Login │ Chat │ Dashboard │ Documents │ Reviews │ Knowledge │
└──────────────────────────────┬──────────────────────────────┘
                               │ /api/
┌──────────────────────────────▼──────────────────────────────┐
│                   Backend (FastAPI + SQLAlchemy)              │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ Master Agent │  │ Sub-Agents   │  │ RAG Pipeline        │ │
│  │ (Orchestrator)│  │ - Compliance │  │ - Chunker           │ │
│  │              │  │ - Comparison │  │ - Retriever         │ │
│  │              │  │ - Drafting   │  │ - Context Builder   │ │
│  │              │  │ - LegalSearch│  │ - Document Processor│ │
│  │              │  │ - Retrieval  │  │                     │ │
│  │              │  │ - Validation │  │                     │ │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────────┘ │
└─────────┼─────────────────┼───────────────────┼──────────────┘
          │                 │                   │
   ┌──────▼─────┐   ┌──────▼──────┐   ┌────────▼────────┐
   │ PostgreSQL │   │   Milvus    │   │   NebulaGraph   │
   │  (元数据)   │   │  (向量库)   │   │   (知识图谱)    │
   └────────────┘   └─────────────┘   └─────────────────┘
   ┌────────────┐   ┌─────────────┐   ┌─────────────────┐
   │   MinIO    │   │    Redis    │   │      Kafka      │
   │ (文件存储)  │   │   (缓存)    │   │   (消息队列)    │
   └────────────┘   └─────────────┘   └─────────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | React 18 + TypeScript + Ant Design 5 + TailwindCSS + Zustand + Vite |
| **后端** | FastAPI + SQLAlchemy 2 (async) + Pydantic v2 + Alembic |
| **AI/LLM** | LangChain + OpenAI SDK + DashScope + Sentence-Transformers + PaddleOCR |
| **向量库** | Milvus 2.5 (standalone) |
| **知识图谱** | NebulaGraph 3.8 |
| **关系库** | PostgreSQL 16 |
| **缓存** | Redis 7 |
| **文件存储** | MinIO |
| **消息队列** | Kafka 7.6 (via aiokafka) |
| **监控** | Prometheus + Grafana + Jaeger (OpenTelemetry) |
| **部署** | Docker Compose / Kubernetes (Docker Desktop) / Helm |

## 功能模块

- **智能对话** - 多轮对话式合同合规审查，支持引用溯源
- **Agent 协同** - 主 Agent 调度 6 个专项子 Agent（合规审查、条款比对、合同起草、法律检索、检索、校验）
- **多模态文档处理** - 支持 PDF/Word/Excel/图片，OCR 识别扫描件，公章/签名检测
- **混合 RAG 检索** - 向量检索 + 全文检索 + 知识图谱推理三路并行，粗排 + 精排 + 自校验
- **知识管理** - 企业合规规则库、法律条文自动同步、文档批量入库（Kafka 异步流水线）
- **评估体系** - A/B 测试面板、召回质量评估、Prompt 版本管理与测试
- **模型管理** - 多模型配置、模型部署管理、A/B 测试
- **可观测性** - Agent 执行追踪、检索质量大盘、系统监控大盘、分布式链路追踪
- **权限与安全** - JWT 认证、RBAC 权限、多租户隔离

## 快速开始

### 前置要求

- Docker Desktop（推荐分配 >= 8 GiB 内存）
- Docker Compose v2

### 启动全部服务

```bash
docker compose up -d
```

首次启动需要拉取镜像，约 3-8 分钟。查看所有容器状态：

```bash
docker compose ps
```

### 访问入口

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3000 | 登录后进入工作台 |
| 后端 API | http://localhost:8000 | Swagger: `/docs` |
| Grafana | http://localhost:3001 | admin / admin123 |
| Prometheus | http://localhost:9090 | scrape 状态 |
| Jaeger | http://localhost:16686 | 分布式追踪 |
| MinIO 控制台 | http://localhost:9001 | minioadmin / minioadmin123 |

### 创建首个用户

首次启动后数据库为空，需要注册管理员账号：

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"password123","full_name":"Admin"}'
```

然后访问 http://localhost:3000 使用 `admin / password123` 登录。

### 热更新

```bash
# 前端 UI 改动
docker compose up -d --build frontend

# 后端已挂载源码并开启 --reload，保存即生效
# 仅当 requirements.txt 变更时需要重建
docker compose up -d --build backend
```

### 停止与清理

```bash
docker compose down          # 停容器，保留数据
docker compose down -v       # 彻底清理（含数据卷）
```

## 部署模式

### 模式 A：Docker Compose（开发/演示）

即上面介绍的快速启动方式，内存约 4 GiB，5-10 分钟启动。

### 模式 B：Kubernetes（Docker Desktop）

模拟生产环境，走完整监控闭环。前置条件：Docker Desktop 启用 K8s、Helm 已安装。

```bash
# 1. 安装监控栈
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f k8s/monitoring/values.yaml

kubectl apply -f k8s/monitoring/

# 2. 构建镜像
docker compose build backend frontend

# 3. 部署应用
kubectl apply -f k8s/local/00-base.yaml
kubectl apply -f k8s/local/10-data.yaml
kubectl apply -f k8s/local/20-milvus.yaml
kubectl apply -f k8s/local/30-kafka.yaml
kubectl apply -f k8s/local/40-nebula.yaml
kubectl apply -f k8s/local/50-app.yaml

# 4. 查看状态
kubectl -n contract-agent get pods -w
```

前端通过 NodePort 访问：http://localhost:30080

卸载：

```bash
kubectl delete -f k8s/local/ --ignore-not-found
kubectl delete -f k8s/monitoring/ --ignore-not-found
helm uninstall kps -n monitoring
kubectl delete namespace monitoring contract-agent --ignore-not-found
```

### 模式 C：本地裸跑（断点调试）

```bash
# 1. 只启动依赖服务
docker compose up -d hidb redis milvus minio kafka nebula-graphd

# 2. 后端
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. 前端
cd frontend
npm install
npm run dev  # http://localhost:5173
```

> 本地裸跑需要配置 hosts 或环境变量，使 `hidb / redis / milvus / kafka / nebula-graphd / minio` 解析到 `127.0.0.1`。

## CI/CD

项目内置本机 CI/CD 脚本（`scripts/ci-cd.ps1` / `scripts/ci-cd.sh`），通过 Makefile 调用：

```bash
make ci          # lint + test
make cd          # build + deploy + verify
make all         # 全链路
make fast        # lint + build + deploy + verify
make auto        # 基于 git diff 智能选择阶段
make build C=backend   # 只构建后端
make deploy SKIP_TEST=1 # 跳过测试直接部署
```

## 项目结构

```
contract-agent/
├── backend/                  # 后端服务
│   ├── app/
│   │   ├── agents/           # Agent 框架（主 Agent + 6 个子 Agent）
│   │   ├── api/v1/           # REST API 路由（auth, documents, retrieval, agents 等）
│   │   ├── core/             # 配置、数据库连接、安全
│   │   ├── middleware/       # 中间件（CORS、安全头、监控）
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── rag/              # RAG 管道（分块、检索、上下文构建、文档处理）
│   │   ├── schemas/          # Pydantic 请求/响应模式
│   │   ├── services/         # 业务服务（LLM、缓存、引用、公章/签名检测等）
│   │   │   └── connectors/   # 外部连接器（Milvus, MinIO, Nebula, Kafka, 法律源）
│   │   └── utils/            # 工具函数
│   ├── alembic/              # 数据库迁移
│   ├── tests/                # 测试
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # 前端服务
│   ├── src/
│   │   ├── pages/            # 页面组件
│   │   │   ├── Auth/         # 登录
│   │   │   ├── Chat/         # 智能对话
│   │   │   ├── Dashboard/    # 系统大盘 / Agent 追踪 / 检索质量
│   │   │   ├── Documents/    # 文档库
│   │   │   ├── Knowledge/    # 企业规则库
│   │   │   ├── ModelConfig/  # 模型管理 / A/B 测试 / 部署
│   │   │   ├── PromptManager/# 提示词管理 / 版本 / 测试
│   │   │   └── Reviews/      # 审查工作台
│   │   ├── components/       # 通用组件
│   │   ├── hooks/            # 自定义 Hooks
│   │   ├── services/         # API 调用
│   │   ├── store/            # Zustand 状态管理
│   │   └── utils/            # 工具函数
│   ├── nginx.conf            # Nginx 反向代理配置
│   ├── Dockerfile
│   └── package.json
├── docker/                   # Docker 配置
│   ├── grafana/              # Grafana provisioning & dashboards
│   └── prometheus/           # Prometheus 配置
├── k8s/                      # Kubernetes manifests
│   ├── local/                # 本地 Docker Desktop K8s 部署
│   ├── monitoring/           # 监控栈（ServiceMonitor, PrometheusRule, Grafana Dashboard）
│   └── overlays/             # Kustomize overlays
├── helm/                     # Helm Chart
├── scripts/                  # 运维脚本
│   ├── ci-cd.ps1             # Windows CI/CD 脚本
│   ├── ci-cd.sh              # Linux/macOS CI/CD 脚本
│   └── init-db.sh            # 数据库初始化
├── docs/                     # 项目文档
├── docker-compose.yml        # Docker Compose 编排（13 个服务）
└── Makefile                  # CI/CD 入口
```

## API 概览

后端 API 版本化前缀为 `/api/v1/`，主要端点：

| 模块 | 路径 | 说明 |
|------|------|------|
| 认证 | `/auth/register`, `/auth/login` | 注册、登录 |
| 文档 | `/documents/` | 上传、列表、状态查询 |
| 检索 | `/retrieval/` | 混合检索、引用溯源 |
| Agent | `/agents/` | Agent 会话、执行、追踪 |
| 评估 | `/evaluation/` | 召回评估、测试集管理 |
| 提示词 | `/prompts/` | 提示词 CRUD、版本管理、测试 |
| 模型 | `/models/` | 模型配置、部署、A/B 测试 |
| 系统 | `/system/` | 健康检查、连接器状态 |

完整 API 文档启动后访问 http://localhost:8000/docs 。

## License

Private - All Rights Reserved
