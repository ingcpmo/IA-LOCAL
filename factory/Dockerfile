FROM python:3.11-slim
WORKDIR /app
COPY factory/requirements.txt /tmp/factory_requirements.txt
RUN pip install --no-cache-dir -r /tmp/factory_requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8000
# W5-F0-1: sin --reload. El código montado en /app/factory solo se recarga
# con un restart explícito y aprobado del contenedor (procedimiento gated):
#   docker compose -f factory/docker-compose.factory.yml restart factory-api
CMD ["uvicorn", "factory.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
