# ──────────────────────────────────────────────────────────────────────────────
# Dockerfile — Backend GLM-OCR  (Hugging Face Spaces — Docker SDK)
# rebuild: 2026-04-08
# Port exposé : 7860  (obligatoire HF Spaces)
# RAM estimée : ~8 Go float16 sur GPU T4
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.10-slim

ARG CACHEBUST=20260408

# ── Variables d'environnement ────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.hf_cache \
    TRANSFORMERS_CACHE=/app/.hf_cache \
    MPLBACKEND=Agg

# ── Dépendances système ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    gcc \
    g++ \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Répertoire de travail ────────────────────────────────────────────────────
WORKDIR /app

# ── Installer les dépendances Python ─────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copier le code source ─────────────────────────────────────────────────────
COPY main.py .
COPY README.md .

# ── Dossiers de cache ─────────────────────────────────────────────────────────
RUN mkdir -p /app/.hf_cache /tmp/uploads

# ── Port HF Spaces ────────────────────────────────────────────────────────────
EXPOSE 7860

# ── Lancement ─────────────────────────────────────────────────────────────────
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
