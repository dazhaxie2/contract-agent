# 本机 Docker Desktop K8s 按需 CI/CD

针对 **Windows + Docker Desktop 内置 Kubernetes** 的开发环境，提供一条命令完成 lint → test → build → deploy → verify 的本机闭环。不依赖云端 runner，所有镜像直接落到 Docker Desktop 共享的 image store，K8s 用 `IfNotPresent` 拉取本地镜像。

---

## 速查

```powershell
# 完整链路（全 stage、全组件）
.\scripts\ci-cd.ps1 all

# 智能：看 git diff 自动选阶段+组件（最常用）
.\scripts\ci-cd.ps1 auto

# 开发循环：跳过 test，只 lint+build+deploy+verify
.\scripts\ci-cd.ps1 fast

# 只跑某组件
.\scripts\ci-cd.ps1 -Component backend all

# 文件变化自动触发
.\scripts\ci-cd.ps1 watch
```

跨平台等价（macOS / Linux / Git Bash）：

```bash
./scripts/ci-cd.sh all
COMPONENT=backend ./scripts/ci-cd.sh fast
SKIP_TEST=1 NO_CACHE=1 ./scripts/ci-cd.sh all
```

或用 Makefile：

```bash
make all
make ci          # lint + test
make cd          # build + deploy + verify
make fast
make auto
make watch
make build C=backend
make status
make clean
```

---

## 阶段

| 阶段 | 做什么 | 失败行为 |
|---|---|---|
| `lint` | backend `ruff check .`、frontend `npm run lint` | backend 严格、frontend 同云端 CI 一样 `continue-on-error` |
| `test` | backend `pytest`（依赖 hidb+redis，自动 `docker compose up -d`） | 严格 |
| `build` | `docker build` 两个组件，打 `:latest` + `:<git-short-sha>` 双 tag | 严格 |
| `deploy` | `kubectl apply -f k8s/local/50-app.yaml` + `kubectl set image` 用 sha tag 强制 rollout | 严格 |
| `verify` | `kubectl rollout status` + pod 内 `curl /health` 6×5s 重试 | 严格 |

阶段组合别名：

| 别名 | 展开 |
|---|---|
| `all` | lint + test + build + deploy + verify |
| `ci` | lint + test |
| `cd` | build + deploy + verify |
| `fast` | lint + build + deploy + verify（开发循环最常用） |
| `auto` | 看 `git diff` 决定（见下） |
| `watch` | 监听 `git status` 变化，每次变化跑一次 `fast` |

---

## 按需触发的三种方式

1. **手动**：上面那些命令，需要时跑。
2. **智能（git diff）**：`./scripts/ci-cd.ps1 auto`
   - 只动 `backend/` → 只跑 backend 全链路
   - 只动 `frontend/` → 只跑 frontend 全链路
   - 只动 `k8s/` 或 `helm/` 或 `docker-compose.yml` → 跳过 lint/test，直接 deploy + verify
   - 没改 → 退化为 lint+test 自检
3. **watch 模式**：`./scripts/ci-cd.ps1 watch` —— 每 3 秒看一次 `git status`，有变化就触发 `fast`。适合"边写边看 K8s 里跑起来"的场景。

---

## 镜像版本与 rollout 触发

K8s 里 `deploy/backend` 和 `deploy/frontend` 默认引用 `:latest`，但 `:latest` 不变 → K8s 不会重启 pod。所以 `build` 阶段同时打了 `:<git-short-sha>` tag，`deploy` 阶段用 `kubectl set image deploy/backend backend=contract-agent-backend:<sha>` 触发 rollout。sha 落在 `.ci-cd.lastbuild`，单独跑 `deploy` 也能拿到最近一次 build 的 tag。

> 想强制重 deploy 同一 sha？用 `kubectl rollout restart deploy/backend`，或重新跑 `build deploy`。

---

## 常用开关

| 开关 (PowerShell) | 等价环境变量 (bash) | 作用 |
|---|---|---|
| `-Component backend\|frontend\|both` | `COMPONENT=` | 限定组件，默认 `both` |
| `-SkipTest` | `SKIP_TEST=1` | 跳过 pytest |
| `-SkipLint` | `SKIP_LINT=1` | 跳过 lint |
| `-NoCache` | `NO_CACHE=1` | `docker build --no-cache` |
| `-DryRun` | — | 只打印不执行（PowerShell 专属） |
| `-KeepGoing` | — | 阶段失败继续后续阶段 |
| `-Context docker-desktop` | `KCTX=` | 指定 kubectl context |
| `-Namespace contract-agent` | `NAMESPACE=` | 指定 ns |
| `-RolloutTimeoutSec 300` | `ROLLOUT_TIMEOUT=` | rollout 等待秒数 |

---

## 首次使用

```powershell
# 1. 确认 Docker Desktop 已启动且开了 Kubernetes
kubectl config use-context docker-desktop
kubectl get nodes

# 2. 一键全量
.\scripts\ci-cd.ps1 all
```

首次会自动按顺序 apply `k8s/local/00-base.yaml` … `50-app.yaml`，之后只 patch `50-app.yaml`（避免重置数据层）。

---

## 与云端 GitHub Actions 的关系

`.github/workflows/ci.yml` / `cd.yml` 继续负责 push 到 ghcr.io 和 staging/production 集群。本机脚本与之**完全独立**，不共用 runner 也不依赖 secrets。两者各自演进。

---

## 故障排查

- **`kubectl 连不上 context=docker-desktop`**：Docker Desktop 设置里 Kubernetes 没开，或没等就绪。
- **pod 一直 `ImagePullBackOff`**：本地 daemon 里没这个 tag。重跑一次 `build deploy`。
- **`/health` 失败**：脚本会自动 dump `kubectl logs deploy/backend --tail=80`，查日志。
- **数据层没起**：`kubectl -n contract-agent get pods` 看 hidb/redis/milvus/kafka/nebula 是不是 Running，否则手动 `kubectl apply -f k8s/local/10-data.yaml`（依此类推）。
- **想完全重来**：`make clean` → `make all`。
