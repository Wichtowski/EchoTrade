FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:/root/.local/bin:$PATH \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browsers \
    ECHO_LENS_ARTIFACTS_DIR=/tmp/echotrade-lens \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY app ./app
COPY make ./make
COPY README.md ./

RUN uv sync --locked --package core --extra migration
RUN /opt/venv/bin/playwright install --with-deps --only-shell chromium && rm -rf /var/lib/apt/lists/*

CMD ["/opt/venv/bin/uvicorn", "core.app:app", "--host", "0.0.0.0", "--port", "8000"]
