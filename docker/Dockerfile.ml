FROM python:3.12-slim-bookworm
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip
COPY pyproject.toml README.md ./
COPY pulserank_ml ./pulserank_ml
COPY services ./services
RUN pip install --no-cache-dir .
EXPOSE 8090
CMD ["uvicorn", "services.ml_service.app:app", "--host", "0.0.0.0", "--port", "8090"]
