FROM python:3.11-slim
WORKDIR /app
COPY factory/requirements.txt /tmp/factory_requirements.txt
RUN pip install --no-cache-dir -r /tmp/factory_requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "factory.api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/app/factory"]
