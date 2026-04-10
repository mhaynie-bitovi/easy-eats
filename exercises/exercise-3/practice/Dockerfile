# Stage 1: Install dependencies
FROM python:3.14-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir temporalio==1.24.0

# Stage 2: Runtime
FROM python:3.14-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY valet/ valet/

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "valet.worker"]
