FROM python:3.11-slim
WORKDIR /app
# H-5F (2026-08-29): iptables/iproute2 para el egress guard en el network
# namespace del contenedor (NETWORK_LEVEL_CONTROL). Sin CUDA, sin ollama pkg.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iptables iproute2 \
    && rm -rf /var/lib/apt/lists/*
COPY factory/requirements.txt /tmp/factory_requirements.txt
RUN pip install --no-cache-dir -r /tmp/factory_requirements.txt
COPY factory/scripts/ops/factory_egress_guard.sh /usr/local/bin/factory_egress_guard.sh
RUN chmod +x /usr/local/bin/factory_egress_guard.sh
ENV PYTHONPATH=/app
EXPOSE 8000
# W5-F0-1: sin --reload. El código montado en /app/factory solo se recarga
# con un restart explícito y aprobado del contenedor (procedimiento gated):
#   docker compose -f factory/docker-compose.factory.yml restart factory-api
# H-5F: ENTRYPOINT = egress guard (deny-by-default OUTPUT, allowlist Ollama
# local). El guard hace exec del CMD al final.
ENTRYPOINT ["/usr/local/bin/factory_egress_guard.sh"]
CMD ["uvicorn", "factory.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
