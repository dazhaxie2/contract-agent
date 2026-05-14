# 监控栈接入说明（kube-prometheus-stack）

本目录把 Prometheus + Grafana + Alertmanager + node-exporter + kube-state-metrics
通过官方 `kube-prometheus-stack` Helm chart 装到独立 namespace `monitoring`，并把
`contract-agent` 命名空间下 backend 的 `/metrics` 端点接入到 Operator 的 ServiceMonitor 体系。

云端 LLM（如 DashScope/OpenAI）本身没有 `/metrics` 可抓——它的可观测性靠 backend
内部埋点上报（`contract_agent_llm_*` 系列指标），详见 `backend/app/middleware/metrics.py`
和 `backend/app/services/llm_service.py`。

---

## 一、首次安装

```bash
# 1. 添加 Helm 仓库
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 2. 创建 namespace
kubectl create namespace monitoring

# 3. 安装 kube-prometheus-stack（使用本目录 values）
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f k8s/monitoring/values.yaml \
  --version "^65.0.0"

# 4. 部署 contract-agent 自己的采集 + 告警 + dashboard
kubectl apply -f k8s/monitoring/servicemonitor.yaml
kubectl apply -f k8s/monitoring/prometheusrule.yaml
kubectl apply -f k8s/monitoring/grafana-dashboard.yaml
```

---

## 二、访问 UI

```bash
# Prometheus
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090
# → http://localhost:9090

# Grafana（默认账号 admin / 见下方密码取法）
kubectl -n monitoring port-forward svc/kps-grafana 3000:80
# → http://localhost:3000

# 取 Grafana 初始密码
kubectl -n monitoring get secret kps-grafana \
  -o jsonpath="{.data.admin-password}" | base64 -d; echo
```

---

## 三、验证 contract-agent 被采集

进入 Prometheus UI 的 `Status → Targets`，应能看到一条
`serviceMonitor/monitoring/contract-agent-backend/0 (UP)`。

或命令行：

```bash
kubectl -n monitoring exec -it sts/prometheus-kps-kube-prometheus-stack-prometheus-0 -- \
  wget -qO- 'http://localhost:9090/api/v1/targets' | grep contract-agent
```

打开 Grafana → Dashboards，应当能看到 **Contract Agent / Overview** 这个面板。

---

## 四、关键指标速查

| 指标 | 含义 |
|---|---|
| `contract_agent_requests_total` | HTTP 总请求数（按 method/path/status_code/tenant_id 分组） |
| `contract_agent_request_duration_seconds_bucket` | HTTP 延迟直方图 |
| `contract_agent_llm_requests_total` | LLM 调用次数（按 model/status 分组） |
| `contract_agent_llm_tokens_total` | LLM Token 消耗（input/output） |
| `contract_agent_llm_duration_seconds_bucket` | LLM 调用延迟直方图 |
| `contract_agent_retrieval_total` | 检索次数（vector/keyword/graph） |
| `contract_agent_cache_hits_total` / `_misses_total` | 缓存命中/未命中 |

---

## 五、告警规则

`prometheusrule.yaml` 中默认开启以下告警（Alertmanager 路由请按你的实际接收方配置）：

- `ContractAgentHigh5xxRate`：5xx 错误率 5 分钟 > 5%
- `ContractAgentP99LatencyHigh`：HTTP P99 延迟 5 分钟 > 2s
- `ContractAgentLLMErrorRateHigh`：LLM 错误率 5 分钟 > 5%
- `ContractAgentLLMLatencyHigh`：LLM 平均延迟 5 分钟 > 10s
- `ContractAgentTargetDown`：backend 实例下线 1 分钟

---

## 六、卸载

```bash
kubectl delete -f k8s/monitoring/grafana-dashboard.yaml
kubectl delete -f k8s/monitoring/prometheusrule.yaml
kubectl delete -f k8s/monitoring/servicemonitor.yaml
helm uninstall kps -n monitoring
kubectl delete namespace monitoring
```
## 七、学习
**Docker 是用来“打包”和“运行”单个容器的，而 Kubernetes 是用来“管理”成百上千个容器的（即容器编排）。**

为了帮你快速上手，我把 k8s 的知识和命令与你熟悉的 Docker 关联起来，这样理解会快很多。

------

### 一、 核心概念：Docker vs Kubernetes

你可以把 Docker 想象成“集装箱”，而 Kubernetes 就是“管理集装箱的港口系统”。

| Docker 的概念                      | Kubernetes 的对应概念           | 它的作用是什么？                                             |
| :--------------------------------- | :------------------------------ | :----------------------------------------------------------- |
| **Container (容器)**               | **Pod (最小调度单元)**          | k8s 中最小的单位是 Pod，而不是容器。一个 Pod 里面可以包含一个或多个关系极其紧密的 Docker 容器。它们共享网络 IP 和存储。 |
| **Image (镜像)**                   | **Image (镜像)**                | 概念一样，k8s 底层依然需要拉取你的 Docker 镜像来运行。       |
| **docker run / docker-compose**    | **Deployment (部署)**           | 在 k8s 中，你通常不会直接创建一个 Pod，而是创建一个 Deployment。它负责保证你的程序一直运行（比如你规定要跑 3 个副本，挂了一个，Deployment 会自动拉起一个新的）。 |
| **docker network / 端口映射 (-p)** | **Service (服务)**              | Pod 的 IP 是会变的（每次重启都会变）。Service 就是一个固定的访问入口（负载均衡器），它将外部请求转发给后面的多个 Pod。 |
| **Docker Volume (-v)**             | **PersistentVolume (PV) / PVC** | 用于数据持久化。Pod 重启数据不会丢。                         |
| **环境变量 (-e) / .env 文件**      | **ConfigMap / Secret**          | 用于把配置和敏感信息（如密码）与镜像解耦。                   |

------

### 二、 日常操作命令对比

你之前用 `docker` 或 `docker-compose` 命令，现在你将主要使用 `kubectl`（k8s 的命令行工具）。

#### 1. 查看运行状态

- **Docker:** `docker ps` (看运行的容器)

- K8s:

  ```
  kubectl get pods
  ```

  (看运行的 Pods)

  - *进阶:* `kubectl get pods -n <命名空间>` (k8s 有命名空间隔离的概念，默认是 default)

#### 2. 查看日志 (排错必备)

- **Docker:** `docker logs -f <container_id>`

- K8s:

  ```
  kubectl logs -f <pod_name>
  ```

  - *进阶:* 如果 Pod 里有多个容器，需要加 `-c <容器名>`。

#### 3. 进入容器内部

- **Docker:** `docker exec -it <container_id> /bin/bash`
- **K8s:** `kubectl exec -it <pod_name> -- /bin/bash` (或者 `/bin/sh`)

#### 4. 查看详细信息 (当你发现容器起不来时)

- **Docker:** `docker inspect <container_id>`

- K8s:

  ```
  kubectl describe pod <pod_name>
  ```

  - **小白避坑指南**：当 `kubectl get pods` 看到状态是 `CrashLoopBackOff` 或 `Pending` 时，第一时间用 `kubectl describe` 和 `kubectl logs` 去看原因！

#### 5. 部署 / 应用更改

- **Docker:** `docker-compose up -d`

- K8s:

  ```
  kubectl apply -f deployment.yaml
  ```

  - k8s 万物皆 YAML。你通常会写一个 `.yaml` 文件来描述你想运行的服务，然后用 apply 提交给 k8s 集群。

#### 6. 删除 / 停止

- **Docker:** `docker rm -f <container_id>` 或 `docker-compose down`
- **K8s:** `kubectl delete pod <pod_name>` (注意：如果你只删 pod，Deployment 会立刻重启一个新的。要彻底删除需要 `kubectl delete deployment <deployment_name>` 或 `kubectl delete -f deployment.yaml`)

------

### 三、 小白上手的标准工作流

在将你的项目部署到 K8s 时，你的工作流通常会变成这样：

1. **写代码 & 写 Dockerfile**（和以前一样）。

2. **构建镜像并推送到镜像仓库**：`docker build ...` 然后 `docker push registry.example.com/my-app:v1`。（k8s 需要从网络上拉取镜像，不能只存在你本地）。

3. 编写 K8s YAML 文件

   ：通常需要写两个：

   - `Deployment.yaml` (告诉 k8s 拉取哪个镜像，运行几个副本)。
   - `Service.yaml` (告诉 k8s 暴露哪个端口，让其他服务能访问它)。

4. **应用到集群**：`kubectl apply -f your-file.yaml`。

### 给新手的两个重要建议：

1. **学会看 YAML 文件**：你正在查看的 `k8s/monitoring/README.md` 这个目录应该就是存放各种 YAML 配置的。不要害怕 YAML，它只是把你在 `docker run` 命令里敲的那些参数变成了配置文件。
2. **理解“状态不可靠”**：在 Docker 里你可能习惯了进容器改个文件。在 k8s 里**绝对不要**这么做。Pod 随时可能被调度到其他机器、重启或者被销毁。任何配置都应该写在 ConfigMap 里，任何数据都应该挂载外部存储，保持容器本身是“无状态”的。