# 合同合规 Agent 原生 AI 工作台开发计划

更新时间：2026-05-14

本文档用于跟踪“合同审查工作台 MVP”到“对话式、计划确认式、跨域协同合同工作台”的整体开发进度。后续每完成一个模块，就在对应条目前勾选，并补充完成记录。

## 维护规则

- `[x]` 表示已开发并通过基础验证。
- `[ ]` 表示未开始或尚未完成闭环。
- 一个功能如果只完成 MVP，则先勾选 MVP 子项，增强项继续保留未勾选。
- 每次完成开发后，同步更新“完成记录”和“下一步优先级”。

## 当前完成记录

- 2026-05-14：完成合同助手主入口升级，`/reviews` 支持对话、计划卡片、确认执行、工具轨迹、报告、引用和反馈。
- 2026-05-14：新增后端 `POST /api/v1/agents/plan` 与 `POST /api/v1/agents/decisions/{decision_id}/execute`。
- 2026-05-14：扩展 `AgentExecution.result_metadata`，写入 `decision_id`、`plan`、`tool_results`、`user_confirmation`、`review_report`。
- 2026-05-14：反馈接口生成 `regression_case_id` 和可回放 regression case。
- 2026-05-14：后端回归 `pytest tests\test_a_phase_closure.py` 通过，前端 `npm run build` 通过，真实 HTTP smoke 通过。
- 2026-05-14：新增 sub-agent 统一输入输出契约，Orchestrator 路由时写入 `agent_contract` 并返回标准化 sub-agent output。
- 2026-05-14：新增真实工作台指标、regression case 列表/详情、20 条脱敏样例和本地回放命令。
- 2026-05-14：新增稳定原子工具清单、workspace 扩展预留 schema、Prompt 测试 trace 展示和文档库快捷审查/版本对比入口。
- 2026-05-14：扩充 20 条脱敏合同审查样例，新增审查报告 DOCX/PDF 导出和批量审查入口。
- 2026-05-14：模型 A/B 页面接入真实 API，Prompt 版本历史展示质量评分和 evaluation_results。
- 2026-05-14：新增 `/auth/me` 权限自检，补充 viewer 写操作 403 的 RBAC 回归测试。
- 2026-05-14：补齐合同工作台 API 端到端验收和失败场景自动化，覆盖空文件、入库失败、无依据、LLM 未配置和 401。
- 2026-05-14：完成项目审查与技术债沉淀，修复认证/刷新令牌状态校验、前端消息 ID、路由懒加载和 pytest 启动配置，详见 `docs/PROJECT_REVIEW_TECH_DEBT.md`。
- 2026-05-14：过完项目审查后续清单，新增持久化 `AgentDecision`、部署初始化 admin 脚本、前端 token 自动刷新、轻量 SVG 图表、异常可观测处理和认证中间件专项测试。

## P0：可演示合同审查闭环

- [x] 修复前端中文文案，统一菜单、标题、按钮、空状态。
- [x] 新增 `/login` 页面，调用 `/api/v1/auth/login`，保存 `access_token` 和 `tenant_id`。
- [x] 补齐前端 API client：documents、sessions、agents、retrieval、citations。
- [x] 新增 `/reviews` 工作台，支持上传合同、填写标题、选择审查类型、查看入库进度。
- [x] 上传成功后创建会话，并围绕当前合同发起审查。
- [x] 结果页展示总体风险、风险条目、合同片段、问题说明、修改建议、引用依据、耗时和 token。
- [x] 使用 `/api/v1/agents/executions?task_type=contract_review` 展示审查历史。
- [x] 检索支持 `filters.doc_id` / `filters.document_ids`，审查只召回目标合同范围。
- [x] `/api/v1/documents/{doc_id}/chunks?full=true` 返回完整 chunk content。
- [x] `contract_review` 生成结构化 `review_report`，同时保留 Markdown result。
- [x] 风险项最小结构包含 `severity`、`clause_excerpt`、`issue`、`legal_basis`、`recommendation`、`confidence`。

## P0：原生 AI 交互与计划确认

- [x] 将 `/reviews` 升级为“对话 + 工作台”混合界面。
- [x] 聊天区承接自然语言输入、计划确认和执行解释。
- [x] 工作台展示合同、风险项、引用、任务进度、工具轨迹和历史记录。
- [x] 新增 `Plan -> Confirm -> Execute -> Report` 后端流程。
- [x] Agent 先把自然语言需求解析为结构化计划。
- [x] 对写入型动作先展示计划，用户确认后再执行。
- [x] 只读 plan 生成不写入 `AgentExecution`。
- [x] 确认执行后写入 `AgentExecution.result_metadata.plan`。
- [x] 确认执行后写入 `review_report`、`decision_id`、`tool_results` 和 `user_confirmation`。
- [x] 保留 `/api/v1/agents/execute` 兼容入口。
- [x] 新增前端类型 `AgentPlan`、`PlanStep`、`DecisionRecord`、`ToolResult`。

## P1：可信度闭环与可观测性

- [x] 引用面板可点击 citation，展示来源文档、章节位置、摘录和 chunk 信息。
- [x] 审查结果支持 1-5 分反馈和备注。
- [x] 用户反馈后保存 regression case 基础数据：输入、计划、工具轨迹、引用、期望修正。
- [x] 无 citation 的风险项在前端标记为“不确定/依据不足”。
- [x] 每次计划生成、用户确认、执行结果绑定 `decision_id`。
- [x] 后端测试覆盖 plan、未确认拒绝执行、确认执行、metadata、反馈回归样例。
- [x] Dashboard 增加计划成功率、工具失败率、引用覆盖率、低置信度占比、用户反馈均分。
- [x] 增加 regression case 列表与回放命令，支持批量跑本地样例。
- [x] Prompt 测试页去掉模拟输出，统一真实调用 `promptApi.test` 并展示 trace。
- [x] 工具调用链路补充更细粒度 span，便于定位具体失败工具。

## P1：文档库

- [x] 新增 `/documents` 页面，展示文档列表、状态、类型、chunk 数、上传时间、失败原因。
- [x] 文档详情展示入库事件、chunk 预览、元数据、生效状态。
- [x] 支持删除文档并刷新列表。
- [x] 文档详情增加版本对比入口。
- [x] 文档列表增加“作为当前合同发起审查”的快捷动作。

## P1：DDD 与 Smart Agent, Dumb Tools 收敛

- [x] 在计划结构中区分 `contract`、`review`、`knowledge`、`observability` 领域步骤。
- [x] Orchestrator 负责计划拆解和确认执行入口。
- [x] 工具轨迹以 `tool_results` 形式沉淀到执行记录。
- [x] 为 `retrieval`、`compliance`、`comparison`、`drafting`、`validation` sub-agent 明确定义统一输入输出契约。
- [x] 将合同域、审查域、知识域的原子工具整理成稳定工具清单。
- [x] 对跨域推理和校验逻辑增加专门 orchestrator 层测试。
- [x] 预留“合同事项/履约事件/费用证据”接口，但不进入 MVP 主流程。

## P2：质量、样例与运营

- [x] 建立 20-50 条脱敏合同审查样例，覆盖付款、违约、解除、保密、责任限制、争议解决。
- [x] 至少 10 条样例纳入自动回放，稳定验证 plan/execute/report。
- [x] 指标页从估算指标升级为真实指标：引用命中率、人工反馈均分、失败率、平均审查耗时。
- [x] 增加导出 DOCX/PDF。
- [x] 增加批量审查。
- [x] 增加模型 A/B 与 prompt 版本效果对比。
- [x] 收敛真实用户体系和 RBAC。

## API 与类型清单

- [x] `POST /api/v1/agents/plan`
  - 输入：`query`、`session_id`、`tenant_id`、`context`、`filters`。
  - 输出：`decision_id`、`intent_summary`、`steps[]`、`requires_confirmation`、`estimated_changes`。
- [x] `POST /api/v1/agents/decisions/{decision_id}/execute`
  - 用户确认后执行计划。
  - 返回 `execution_id`、`trace_id`、`review_report`、`plan`、`tool_results`。
- [x] `/api/v1/agents/execute`
  - 保留兼容入口。
  - `task_type=contract_review` 时返回 Markdown result 和结构化 `review_report`。
- [x] `/api/v1/retrieval/search`
  - 支持 `filters.doc_id` / `filters.document_ids`。
- [x] `/api/v1/documents/{doc_id}/chunks?full=true`
  - 返回完整 chunk content。
- [x] 前端类型：`DocumentItem`、`IngestionJob`、`AgentExecution`、`ReviewReport`、`RiskItem`、`CitationDetail`。
- [x] 前端类型：`AgentPlan`、`PlanStep`、`DecisionRecord`、`ToolResult`。
- [x] 后端类型：`SubAgentTaskInput`、`SubAgentTaskOutput`、`SubAgentFinding`、`SubAgentReference`、`SubAgentToolResult`。
- [x] 后端 API：`GET /api/v1/agents/regression-cases` 与 `GET /api/v1/agents/regression-cases/{id}`。
- [x] 后端 API：`GET /api/v1/agents/tool-catalog` 与 `GET /api/v1/agents/workspace-extension-schema`。
- [x] 后端 API：`GET /api/v1/agents/executions/{execution_id}/export?format=markdown|docx|pdf`。
- [x] 后端 API：`GET /api/v1/auth/me` 返回当前用户、租户、角色和权限。
- [x] 后端命令：`python scripts\replay_regression_cases.py`。

## 测试计划

- [x] 后端：上传合同 `sync=true` 后能查到 document、job、chunks。
- [x] 后端：两个合同同时存在时，`filters.doc_id` 只召回目标合同 chunk。
- [x] 后端：`contract_review` 返回 Markdown result，并在 metadata 中包含 `review_report.risk_items`。
- [x] 后端：风险项引用的 citation 可通过 `/api/v1/citations/{id}` 查询。
- [x] 后端：自然语言请求能生成稳定 `AgentPlan`，包含可执行 step 和 `decision_id`。
- [x] 后端：未确认的写操作不会创建 `AgentExecution`。
- [x] 后端：确认后能按计划执行合同审查，并保留 trace、tool result、review report。
- [x] 后端：用户反馈能生成可回放 regression case。
- [x] 后端：sub-agent 统一契约可完成 input/output roundtrip，并保留引用、工具结果和 findings。
- [x] 后端：regression case 列表/详情可查询，真实工作台指标可从 `/system/metrics/overview` 返回。
- [x] 后端：20 条脱敏合同审查样例可通过本地命令回放。
- [x] 后端：审查报告可导出 Markdown、DOCX、PDF。
- [x] 后端：RBAC 可阻止 viewer 执行模型写操作。
- [x] 后端：orchestrator 路由工具返回标准 sub-agent output。
- [x] 前端：`npm run build` 通过，无 TypeScript 错误。
- [x] HTTP smoke：登录 -> 创建 session -> 生成 plan。
- [x] API 端到端验收：登录 -> 上传合同 -> 等待入库 -> 生成计划 -> 确认执行 -> 查看风险项 -> 展开引用 -> 提交反馈。
- [x] 失败场景：空文件、入库失败、无检索结果、LLM 未配置、401 过期跳登录。

## 下一步优先级

1. 当前计划内开发项已完成并勾选，后续进入演示打磨和真实用户试用。
2. 可继续补充真实浏览器录屏、50 条样例回放、企业制度知识库和 DOCX/PDF 版式优化。
