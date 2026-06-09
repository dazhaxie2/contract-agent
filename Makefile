# ==============================================================
# 本机 Docker Desktop K8s 按需 CI/CD 入口
# ==============================================================
# 用法：
#   make ci           # lint + test
#   make cd           # build + deploy + verify
#   make all          # 全链路
#   make fast         # lint + build + deploy + verify（开发循环）
#   make auto         # 看 git diff 智能选阶段
#   make watch        # 文件变化触发 fast
#   make build C=backend     # 只 build backend
#   make deploy SKIP_TEST=1
# ==============================================================

SHELL := /bin/bash

C ?= both
SKIP_TEST ?= 0
SKIP_LINT ?= 0
NO_CACHE ?= 0

# Windows PowerShell 优先；其他平台用 bash
ifeq ($(OS),Windows_NT)
  CICD := powershell -NoProfile -ExecutionPolicy Bypass -File scripts/ci-cd.ps1
  PS_ARGS := -Component $(C)
  ifeq ($(SKIP_TEST),1)
    PS_ARGS += -SkipTest
  endif
  ifeq ($(SKIP_LINT),1)
    PS_ARGS += -SkipLint
  endif
  ifeq ($(NO_CACHE),1)
    PS_ARGS += -NoCache
  endif
  RUN = $(CICD) $(PS_ARGS)
else
  CICD := bash scripts/ci-cd.sh
  SH_ENV := COMPONENT=$(C) SKIP_TEST=$(SKIP_TEST) SKIP_LINT=$(SKIP_LINT) NO_CACHE=$(NO_CACHE)
  RUN = $(SH_ENV) $(CICD)
endif

.PHONY: help all ci cd fast auto watch lint test build deploy verify clean status

help:
	@echo "本机 CI/CD 入口（Docker Desktop K8s）"
	@echo "  make all       全链路"
	@echo "  make ci        lint + test"
	@echo "  make cd        build + deploy + verify"
	@echo "  make fast      lint + build + deploy + verify"
	@echo "  make auto      智能（基于 git diff）"
	@echo "  make watch     文件变化自动触发 fast"
	@echo "  make build [C=backend|frontend]"
	@echo "  make deploy [C=backend|frontend]"
	@echo "  make verify"
	@echo "  make clean     清理 image / 部署"
	@echo "  make status    查看 deploy / pods 状态"

all:    ; $(RUN) all
ci:     ; $(RUN) ci
cd:     ; $(RUN) cd
fast:   ; $(RUN) fast
auto:   ; $(RUN) auto
watch:  ; $(RUN) watch
lint:   ; $(RUN) lint
test:   ; $(RUN) test
build:  ; $(RUN) build
deploy: ; $(RUN) deploy
verify: ; $(RUN) verify

status:
	@kubectl --context docker-desktop -n contract-agent get deploy,pods -o wide || true

clean:
	@echo "清理本机 K8s 部署 + 镜像"
	-kubectl --context docker-desktop -n contract-agent delete deploy backend frontend --ignore-not-found
	-docker image rm contract-agent-backend:latest contract-agent-frontend:latest 2>/dev/null || true
	-rm -f .ci-cd.lastbuild
