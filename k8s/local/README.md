# 本地 K8s 部署（Docker Desktop）

针对 **Docker Desktop K8s** 优化的一键部署方案——把 contract-agent 整套（backend / frontend / 所有依赖）放到 K8s 里跑，
用 `kube-prometheus-stack` 监控闭环。

> 与 `k8s/base/` 的区别：`base/` 是按 production 写的（多副本、HPA、readOnlyRootFilesystem 等），
> 本目录是单副本、宽松 securityContext、复用本地 docker build 镜像，适合 Docker Desktop。

## 文件目录

| 文件 | 内容 |
|---|---|
| `00-base.yaml` | namespace + ServiceAccount + ConfigMap + Secret + frontend nginx ConfigMap |
| `10-data.yaml` | PostgreSQL (hidb) + Redis + MinIO + etcd |
| `20-milvus.yaml` | Milvus standalone（依赖 etcd + minio） |
| `30-kafka.yaml` | Zookeeper + Kafka |
| `40-nebula.yaml` | Nebula metad + storaged + graphd + init Job |
| `50-app.yaml` | contract-agent backend + frontend + Service |

## 部署

```powershell
# 0. 确保 contract-agent-backend:latest / contract-agent-frontend:latest 已 build
docker compose build backend frontend

# 1. 按序 apply（前面的 ready 后再上下一个不强制，但建议）
kubectl apply -f k8s/local/00-base.yaml
kubectl apply -f k8s/local/10-data.yaml
kubectl apply -f k8s/local/20-milvus.yaml
kubectl apply -f k8s/local/30-kafka.yaml
kubectl apply -f k8s/local/40-nebula.yaml
kubectl apply -f k8s/local/50-app.yaml

# 2. 等所有 Pod Ready
kubectl -n contract-agent get pods -w

# 3. 此时 ServiceMonitor（已在 k8s/monitoring/ apply 过）自动开始抓 backend /metrics
```

## 访问

```powershell
# Frontend（NodePort 30080）
# 浏览器 → http://localhost:30080

# 也可端口转发
kubectl -n contract-agent port-forward svc/frontend 3002:80

# Backend Swagger（可选）
kubectl -n contract-agent port-forward svc/backend 8001:8000
# → http://localhost:8001/docs
```

## 卸载

```powershell
kubectl delete -f k8s/local/ --ignore-not-found
# 注意：PVC 默认不会被删，需要手动清理数据
kubectl -n contract-agent delete pvc --all
```

## 已知限制

1. **资源紧张**：Docker Desktop K8s 默认 ~7.6 GiB 内存，整套吃 ~4.5 GiB，加上 kube-prometheus-stack ~1.5 GiB，剩 1.5 GiB 给系统。如果 OOMKill 出现，可在 Docker Desktop Settings → Resources 调大。
2. **单副本**：所有服务 replicas=1，且数据 PVC 仅 hostPath，不要用作多节点测试。
3. **凭证**：`00-base.yaml` 里 Secret 是开发用占位值（hidb123 / minioadmin123 等），切勿用于生产。
