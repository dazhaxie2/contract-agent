#!/usr/bin/env bash
# =====================================================================
# 本机 Docker Desktop K8s 按需 CI/CD - bash 入口
# ---------------------------------------------------------------------
# 与 scripts/ci-cd.ps1 的子集对齐。给 macOS / Linux / Git Bash 用。
# 用法:
#   ./scripts/ci-cd.sh all
#   ./scripts/ci-cd.sh ci
#   ./scripts/ci-cd.sh cd
#   ./scripts/ci-cd.sh build deploy
#   COMPONENT=backend ./scripts/ci-cd.sh all
#   SKIP_TEST=1 NO_CACHE=1 ./scripts/ci-cd.sh all
# =====================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KCTX:-docker-desktop}"
NS="${NAMESPACE:-contract-agent}"
COMPONENT="${COMPONENT:-both}"      # backend | frontend | both
SKIP_TEST="${SKIP_TEST:-0}"
SKIP_LINT="${SKIP_LINT:-0}"
NO_CACHE="${NO_CACHE:-0}"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-300}"

ts() { date +%H:%M:%S; }
info() { printf '\033[36m[%s] %s\033[0m\n' "$(ts)" "$*"; }
ok()   { printf '\033[32m[%s] OK  %s\033[0m\n' "$(ts)" "$*"; }
warn() { printf '\033[33m[%s] WRN %s\033[0m\n' "$(ts)" "$*"; }
fail() { printf '\033[31m[%s] ERR %s\033[0m\n' "$(ts)" "$*"; }
step() { printf '\n\033[35m==> [%s] %s\033[0m\n' "$(ts)" "$*"; }

is_backend()  { [[ "$COMPONENT" == "both" || "$COMPONENT" == "backend"  ]]; }
is_frontend() { [[ "$COMPONENT" == "both" || "$COMPONENT" == "frontend" ]]; }

git_sha() { git -C "$REPO_ROOT" rev-parse --short=12 HEAD 2>/dev/null || date +%Y%m%d%H%M%S; }

assert_prereqs() {
  step "环境预检"
  command -v docker >/dev/null || { fail "找不到 docker"; exit 1; }
  docker info >/dev/null 2>&1 || { fail "docker daemon 未就绪"; exit 1; }
  ok "docker daemon 可用"
  if [[ "${NEED_K8S:-0}" == "1" ]]; then
    command -v kubectl >/dev/null || { fail "找不到 kubectl"; exit 1; }
    kubectl --context "$CONTEXT" cluster-info >/dev/null 2>&1 \
      || { fail "kubectl 连不上 context=$CONTEXT"; exit 1; }
    ok "kubectl context=$CONTEXT 可用"
  fi
}

stage_lint() {
  step "Lint"
  [[ "$SKIP_LINT" == "1" ]] && { warn "SKIP_LINT=1，跳过"; return; }
  if is_backend; then
    info "backend: ruff"
    (cd "$REPO_ROOT/backend" && python -m pip install --quiet ruff && python -m ruff check .)
    ok "backend ruff 通过"
  fi
  if is_frontend; then
    info "frontend: npm run lint"
    [[ -d "$REPO_ROOT/frontend/node_modules" ]] || (cd "$REPO_ROOT/frontend" && npm ci)
    (cd "$REPO_ROOT/frontend" && npm run lint) || warn "frontend lint 有告警 (continue-on-error)"
  fi
}

stage_test() {
  step "Test"
  [[ "$SKIP_TEST" == "1" ]] && { warn "SKIP_TEST=1，跳过"; return; }
  if is_backend; then
    info "确保 hidb / redis 跑着"
    for s in hidb redis; do
      st=$(docker inspect -f '{{.State.Status}}' "contract-agent-$s" 2>/dev/null || echo missing)
      [[ "$st" == "running" ]] || (cd "$REPO_ROOT" && docker compose up -d "$s")
    done
    cd "$REPO_ROOT/backend"
    DB_PROVIDER=hidb_pg DB_HOST=localhost DB_PORT=5432 DB_USER=hidb DB_PASSWORD=hidb123 \
      DB_NAME=contract_agent DB_READ_TARGET=hidb DB_DUAL_WRITE_ENABLED=false \
      DB_AUTO_CREATE_SCHEMA=false REDIS_HOST=localhost REDIS_PORT=6379 ENVIRONMENT=test \
      python -m pytest tests/ -q
    ok "backend pytest 通过"
  fi
  is_frontend && warn "frontend 暂无单元测试，跳过"
}

stage_build() {
  step "Build"
  local sha; sha="$(git_sha)"
  echo "$sha" > "$REPO_ROOT/.ci-cd.lastbuild"
  local cache=""; [[ "$NO_CACHE" == "1" ]] && cache="--no-cache"
  if is_backend; then
    docker build $cache -t contract-agent-backend:latest -t "contract-agent-backend:$sha" "$REPO_ROOT/backend"
    ok "backend image sha=$sha"
  fi
  if is_frontend; then
    docker build $cache -t contract-agent-frontend:latest -t "contract-agent-frontend:$sha" "$REPO_ROOT/frontend"
    ok "frontend image sha=$sha"
  fi
}

stage_deploy() {
  step "Deploy"
  local sha
  if [[ -f "$REPO_ROOT/.ci-cd.lastbuild" ]]; then sha="$(cat "$REPO_ROOT/.ci-cd.lastbuild")"; else sha="$(git_sha)"; fi

  if ! kubectl --context "$CONTEXT" get ns "$NS" >/dev/null 2>&1; then
    info "ns=$NS 不存在，初始化 k8s/local"
    for f in 00-base.yaml 10-data.yaml 20-milvus.yaml 30-kafka.yaml 40-nebula.yaml 50-app.yaml; do
      kubectl --context "$CONTEXT" apply -f "$REPO_ROOT/k8s/local/$f"
    done
  else
    kubectl --context "$CONTEXT" apply -f "$REPO_ROOT/k8s/local/50-app.yaml"
  fi

  is_backend  && kubectl --context "$CONTEXT" -n "$NS" set image deploy/backend  "backend=contract-agent-backend:$sha"
  is_frontend && kubectl --context "$CONTEXT" -n "$NS" set image deploy/frontend "frontend=contract-agent-frontend:$sha"
  ok "deploy 完成 sha=$sha"
}

stage_verify() {
  step "Verify"
  is_backend  && kubectl --context "$CONTEXT" -n "$NS" rollout status deploy/backend  --timeout="${ROLLOUT_TIMEOUT}s"
  is_frontend && kubectl --context "$CONTEXT" -n "$NS" rollout status deploy/frontend --timeout="${ROLLOUT_TIMEOUT}s"
  if is_backend; then
    for i in $(seq 1 6); do
      if kubectl --context "$CONTEXT" -n "$NS" exec deploy/backend -- curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        ok "backend /health 通过"; return
      fi
      sleep 5
    done
    kubectl --context "$CONTEXT" -n "$NS" logs deploy/backend --tail=80
    fail "backend /health 失败"; exit 1
  fi
}

expand() {
  local out=()
  for s in "$@"; do
    case "$s" in
      all)  out+=(lint test build deploy verify) ;;
      ci)   out+=(lint test) ;;
      cd)   out+=(build deploy verify) ;;
      fast) out+=(lint build deploy verify) ;;
      *)    out+=("$s") ;;
    esac
  done
  printf '%s\n' "${out[@]}"
}

main() {
  [[ $# -eq 0 ]] && set -- all
  mapfile -t STAGES < <(expand "$@")
  for s in "${STAGES[@]}"; do
    [[ "$s" == "deploy" || "$s" == "verify" ]] && export NEED_K8S=1
  done
  assert_prereqs
  for s in "${STAGES[@]}"; do
    case "$s" in
      lint)   stage_lint ;;
      test)   stage_test ;;
      build)  stage_build ;;
      deploy) stage_deploy ;;
      verify) stage_verify ;;
      *) fail "未知阶段 $s"; exit 1 ;;
    esac
  done
  ok "全部阶段通过"
}

main "$@"
