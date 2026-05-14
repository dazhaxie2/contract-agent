# 项目审查、隐藏 Bug 与技术债沉淀

更新时间：2026-05-14

本文档记录本轮项目审查结论：优先排查认证链路、真实接口替换、前端构建健康度、可回归验证和后续经验。

## 本轮已完成

- [x] 认证中间件不再信任 JWT 内的 `role`，每次 Bearer 请求都会回查数据库用户、租户和启用状态。
- [x] `/api/v1/auth/refresh` 不再只校验 refresh token 签名，会回查用户是否仍存在且启用。
- [x] 补充回归测试：不存在用户的旧 token 返回 401，viewer 写模型配置返回 403，停用用户 access/refresh 均被拒绝。
- [x] 前端运行时代码清理 `Math.random` 消息 ID，改为 `crypto.randomUUID`，避免 key 碰撞和不稳定渲染。
- [x] 前端路由改为页面级懒加载，降低首屏加载压力，把后台页按需拆包。
- [x] 新增 `backend/pytest.ini`，在 backend 目录直接运行 `pytest tests -q` 不再依赖手动设置 `PYTHONPATH`。
- [x] 复扫运行时代码中的 `mock`、`fake`、`模拟`、`Math.random`、`console.log`、`TODO/FIXME` 明显信号，当前未发现业务代码残留。
- [x] 将 `decision_id` 从进程内存升级为 `agent_decisions` 持久化表，并补 Alembic migration。
- [x] 公开注册不再自动创建 admin，admin 改为部署初始化脚本创建或提升。
- [x] 前端接入 refresh token 自动续期和 401 请求重放。
- [x] 移除 `@ant-design/charts`，用轻量 SVG 图表替换 Dashboard/模型/A-B 页面图表。
- [x] 清理运行时代码中的静默 `pass`，缓存/监控/清理失败写 debug，评估失败进入执行 metadata。
- [x] 新增认证中间件独立测试，覆盖删除用户、伪造角色、租户不匹配和 API key 路径。
- [x] 完成验证：后端 `pytest tests -q` 通过，前端 `npm run build` 通过，生产依赖 `npm audit --omit=dev` 无漏洞。

## 关键问题与处理

### 1. JWT 角色可被陈旧 token 放大

问题：认证中间件原先主要依赖 token payload 注入 `user_role`。如果用户被删除、停用或角色被调整，旧 token 在过期前仍可能携带旧角色进入业务路由。

处理：Bearer 认证阶段回查 `users` 表，并以数据库中的 `id`、`username`、`role`、`tenant_id`、`is_active` 为准。不存在用户返回 401，停用用户返回 403。

经验：token 只能作为身份线索，权限和用户状态必须以服务端状态为准。

### 2. refresh token 可绕过用户状态校验

问题：`/auth/refresh` 是公开接口，原先只校验 refresh token 是否有效，没有确认用户是否仍存在或启用。

处理：refresh 时解析 `sub` 和 `tenant_id` 后回查用户，用户不存在返回 401，用户停用返回 403，并用数据库中的角色重新签发 token。

经验：登录、请求中间件、刷新令牌三处必须遵循同一套身份状态规则。

### 3. 前端消息 ID 使用随机数

问题：`Date.now() + Math.random()` 会让 React key 不可预测，也不利于测试和调试。

处理：优先使用 `crypto.randomUUID()`，旧环境降级到当前消息序号组合。

经验：UI 临时 ID 也要确定“唯一性来源”，不要用随机数掩盖状态建模问题。

### 4. 前端首屏包过大

问题：所有页面同步 import，会把模型、Prompt、Dashboard、审查工作台等后台页面打进首屏。

处理：`App.tsx` 改为 `React.lazy` + `Suspense` 的路由级懒加载。

追加处理：后续已移除 `@ant-design/charts`，改用轻量 SVG 图表；Ant Design 公共块保留，作为当前后台框架的可接受体积基线。

### 5. 测试启动依赖隐式环境

问题：在 `backend` 目录直接执行 `pytest tests -q` 会因缺少 `PYTHONPATH=.` 找不到 `app` 包。

处理：新增 `backend/pytest.ini` 固化 `pythonpath = .`。

经验：常用验证命令必须开箱即用，不能只存在于某个人的终端习惯里。

### 6. decision_id 只存在进程内存

问题：计划确认链路用内存字典保存决策记录，服务重启或多实例部署时，用户刚看到的计划会无法确认执行。

处理：新增 `AgentDecision` / `agent_decisions` 表，`/agents/plan` 写入持久化决策记录，`/agents/decisions/{decision_id}/execute` 从数据库读取并更新状态。

经验：Plan -> Confirm -> Execute 是产品状态机，不是临时变量；只要用户能看见并稍后点击确认，就应该落库。

### 7. 公开注册自动 bootstrap admin

问题：公开 `/auth/register` 根据“租户首个用户”自动授予 admin，在真实多租户或公网环境里风险过高。

处理：公开注册统一创建 viewer；新增 `backend/scripts/create_admin_user.py`，通过部署环境变量创建或提升 admin。

经验：admin 初始化属于部署动作，不属于普通用户注册路径。

### 8. refresh token 前端链路缺失

问题：后端提供 `/auth/refresh`，但前端 401 只清 token 跳登录，接口存在但产品链路没闭环。

处理：axios response interceptor 增加单飞 refresh，成功后重放原请求；刷新失败才清理登录态并跳转 `/login`。

经验：只要保留 refresh API，就要有前端、后端、测试三方一致的状态机。

### 9. 图表依赖体积过大

问题：`@ant-design/charts` 为少量基础折线/柱状图引入大块依赖，懒加载后仍产生 1.4MB 级别 charts chunk。

处理：移除 `@ant-design/charts`，新增轻量 SVG `SimpleLineChart` / `SimpleBarChart`。构建模块数从 5959 降到 3274，charts chunk 消失。

经验：后台指标页优先展示清楚和稳定，简单趋势图不需要重型可视化运行时。

### 10. 异常静默吞没

问题：缓存、监控、检索缓存写入、画像抽取、LLM-as-Judge 评分等路径存在 `except ...: pass`，排障时容易丢失真实原因。

处理：低风险辅助路径写 debug；LLM-as-Judge 评分失败进入 `AgentExecution.result_metadata.agent_metadata.evaluation_error`。

经验：允许降级，不等于允许失踪。每个被吞掉的异常至少要有一个可观测出口。

## 后续审查清单

- [x] 将 in-memory `decision_id` 存储升级为可持久化决策记录，避免服务重启后计划无法确认执行。
- [x] 将注册接口的“首个租户用户自动 admin”收敛到部署初始化流程，真实多租户场景不建议公开保留。
- [x] 为 `/api/v1/auth/refresh` 增加前端刷新逻辑或明确移除未使用入口，避免接口存在但产品链路未闭环。
- [x] 为图表依赖做 bundle 分析，决定继续保留 `@ant-design/charts` 还是替换轻量图表。
- [x] 将异常吞掉后 `pass` 的路径分级处理：监控失败可 debug，评分失败/检索失败应进入 trace 或 tool_results。
- [x] 为认证中间件增加独立单测，覆盖删除用户、角色变更、租户不匹配、API key 路径。

## 本轮验证记录

- `backend`: `pytest tests -q`，23 passed，1 个第三方 `python_multipart` PendingDeprecationWarning。
- `frontend`: `npm run build`，通过，无 chunk size warning；生产依赖 `npm audit --omit=dev` 为 0 vulnerabilities。
