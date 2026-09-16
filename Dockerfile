FROM ghcr.io/astral-sh/uv:0.12.9 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    NL2OPT_HOST=0.0.0.0 NL2OPT_PORT=8765

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home app

ARG NL2OPT_REVISION=unversioned
ENV NL2OPT_REVISION=$NL2OPT_REVISION
USER app
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; t=os.environ.get('NL2OPT_API_TOKEN',''); r=urllib.request.Request('http://127.0.0.1:'+os.environ.get('PORT',os.environ.get('NL2OPT_PORT','8765'))+'/api/v1/nl2opt/health',headers={'Authorization':'Bearer '+t} if t else {}); urllib.request.urlopen(r,timeout=2).read()"
CMD ["python", "-m", "nl2opt.api"]
