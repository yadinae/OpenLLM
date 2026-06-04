# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app
COPY . .

# 安装构建依赖 + 项目
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir .


# ── 运行镜像 ──────────────────────────────
FROM python:3.11-slim-bookworm

WORKDIR /app

# 运行时依赖仅 uvicorn + httpx（FastAPI 等已随 pip install . 安装）
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/openllm /usr/local/bin/openllm
COPY --from=builder /app/openllm.yaml /app/openllm.yaml
COPY --from=builder /app/.env.example /app/.env

# 健康检查 — 使用 curl 探测 /health 端点
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 11343

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:11343/health || exit 1

USER nobody

ENV HOST=0.0.0.0
ENV PORT=11343

CMD ["openllm", "serve", "--host", "0.0.0.0"]
