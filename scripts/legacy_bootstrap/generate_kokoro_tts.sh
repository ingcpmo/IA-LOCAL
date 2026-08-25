#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/home/ing_cpmo/ARIA/03-code/src}"
SERVICE_DIR="${PROJECT_ROOT}/services/kokoro-tts"
APP_DIR="${SERVICE_DIR}/app"

echo "[INFO] Project root: ${PROJECT_ROOT}"
mkdir -p "${APP_DIR}"

cat > "${SERVICE_DIR}/requirements.txt" <<'EOF'
fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.3
EOF

cat > "${APP_DIR}/__init__.py" <<'EOF'
# kokoro-tts package
EOF

cat > "${APP_DIR}/main.py" <<'EOF'
from __future__ import annotations

import io
import math
import wave
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field


app = FastAPI(title="aria-kokoro-tts", version="0.1.0")


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: str = Field(default="af_sarah")
    sample_rate: int = Field(default=24000, ge=8000, le=48000)
    format: Literal["wav"] = "wav"


def generate_tone_wav(duration_seconds: float = 0.8, sample_rate: int = 24000) -> bytes:
    frames = int(duration_seconds * sample_rate)
    amplitude = 9000
    frequency = 440.0

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(frames):
            envelope = math.sin(math.pi * (i / max(frames, 1)))
            sample = int(amplitude * envelope * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
            wav_file.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))
    return buffer.getvalue()


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "kokoro-tts", "mode": "placeholder"})


@app.post("/synthesize")
async def synthesize(payload: SynthesizeRequest) -> Response:
    duration = max(0.6, min(2.0, len(payload.text) * 0.03))
    wav_bytes = generate_tone_wav(duration_seconds=duration, sample_rate=payload.sample_rate)
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "X-TTS-Mode": "placeholder",
            "X-TTS-Voice": payload.voice,
        },
    )
EOF

cat > "${SERVICE_DIR}/Dockerfile" <<'EOF'
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8002

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
EOF

echo "[PASS] services/kokoro-tts creado en ${SERVICE_DIR}"

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    (cd "${PROJECT_ROOT}" && docker compose -f docker-compose.local.yml build kokoro-tts >/dev/null)
    echo "[PASS] Build de kokoro-tts OK"
  elif command -v docker-compose >/dev/null 2>&1; then
    (cd "${PROJECT_ROOT}" && docker-compose -f docker-compose.local.yml build kokoro-tts >/dev/null)
    echo "[PASS] Build de kokoro-tts OK"
  else
    echo "[WARN] No se encontro compose para validar build"
  fi
fi
