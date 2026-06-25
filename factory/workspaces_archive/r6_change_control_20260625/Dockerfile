FROM python:3.11-slim

LABEL description="GMP Change Control Module — r6_change_control"
LABEL regulatory_scope="21 CFR Part 11 / ALCOA+"
LABEL pending_documents="ICH Q10, FDA Process Validation 2011, ISPE GAMP 5"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
