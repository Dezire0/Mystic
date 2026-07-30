# Build from the repository root: docker build -f runners/linux/Dockerfile .
# Pin the base image digest in deployment automation before production use.
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/mystic
COPY pyproject.toml README.md ./
COPY mystic ./mystic
COPY scripts ./scripts
RUN pip install --no-cache-dir .

RUN groupadd --gid 10001 mystic && useradd --uid 10001 --gid 10001 --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin mystic
USER 10001:10001
ENTRYPOINT ["python", "scripts/mystic_engine_runner.py", "--start"]
