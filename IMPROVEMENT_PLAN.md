# 合同合规Agent系统改进计划

基于《AI智能体开发笔记》对照分析，按优先级执行。

---

## P0 - 核心架构

### 1. 多Agent协同架构
- [x] 创建 OrchestratorAgent 编排器 (`backend/app/agents/orchestrator.py`)
- [x] 实现意图路由分发机制 (`_IntentRoutingTool`)
- [x] 拆分专项子Agent（检索/合规审查/比对/起草/校验/法条搜索）(`backend/app/agents/sub_agents/`)
- [x] 每个子Agent独立system prompt + 工具集

### 2. 对话式交互UI
- [x] 创建 ChatPanel 聊天组件 (`frontend/src/components/Chat/ChatPanel.tsx`)
- [x] 实现流式消息渲染（SSE + JSON 协议）(`ChatPanel.sendStreamingMessage`)
- [x] 对话历史持久化（zustand persist）
- [x] 保留结构化页面作为快速入口（ReviewWorkspace 保留）

## P1 - 质量保障

### 3. 前端全局状态管理
- [x] 创建 zustand store（auth/session/cache）(`frontend/src/store/index.ts`)
- [x] 重构现有组件使用全局store（MainLayout 已接入 auth store）
- [x] localStorage 持久化（zustand persist middleware）

### 4. 长期记忆体系完善
- [x] LLM结构化事实抽取（替代正则）(`session_memory_service._llm_extract_facts`)
- [x] 用户画像记忆模型 (`models/memory.UserProfile`)
- [x] 用户画像 LLM 自动提取 (`session_memory_service.extract_profile_from_text`)
- [x] 用户画像注入 Agent 上下文 (`agents.py` + `base._format_context`)
- [x] 企业合规规则记忆（UserProfile.compliance_rules 字段 + update_user_profile API）

### 5. 生成后事实性校验闭环
- [x] Agent执行后自动 LLM-as-Judge 评分 (`agents.py execute_agent`)
- [x] 评分结果写入 relevance_score / factuality_score
- [x] 校验服务独立模块化 (`services/evaluation_service.py`)
- [x] 评估 API 路由 (`api/v1/evaluation.py` → `/evaluation/score`, `/evaluation/batch`, `/evaluation/metrics`)

## P2 - 基础设施

### 6. 评估体系
- [x] LLM-as-judge 自动评分服务 (`services/evaluation_service.py`)
- [x] 批量评分 + 指标聚合 API
- [x] 前端 evaluation API 对接 (`services/api.ts evaluationApi`)
- [ ] 合同合规领域测试集（1000+ 问答对）— 需法务专家构建
- [ ] CI 离线评估流水线 — 需接入测试集后搭建

### 7. Redis缓存落地
- [x] 缓存服务框架 (`services/cache_service.py`)
- [x] 嵌入结果缓存 (EmbeddingCache)
- [x] 检索结果缓存 (RetrievalCache，已集成到 retriever.py)
- [x] 对话上下文缓存 (ContextCache)

### 8. Token计数精确化
- [x] tiktoken 替换 len//4 估算 (`session_memory_service._rough_token_count`)
- [x] 优雅降级（tiktoken 不可用时回退到字符估算）
