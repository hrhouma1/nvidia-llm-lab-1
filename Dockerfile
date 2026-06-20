# syntax=docker/dockerfile:1

# --- Etape 1 : build des dependances dans un venv isole ---
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# --- Etape 2 : image finale, legere et sans outils de build ---
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Utilisateur non-root (bonne pratique securite)
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app.py nvidia_client.py web_search.py ./

USER appuser

EXPOSE 8501

# Verifie que Streamlit repond sur son endpoint de sante
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)"

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
