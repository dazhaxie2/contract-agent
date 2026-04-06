# ============================================
# 合同合规Agent系统 - 后端多阶段构建
# ============================================

# ---------- 阶段1: 依赖安装 ----------
FROM python:3.12-slim AS builder

WORKDIR /build

# 安装系统级构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- 阶段2: 运行时镜像 ----------
FROM python:3.12-slim AS runtime

# 安全：创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从builder阶段复制已安装的Python包
COPY --from=builder /install /usr/local

# 复制应用代码
COPY . .

# 设置文件所有权
RUN chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 暴露服务端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 使用gunicorn + uvicorn worker启动
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
