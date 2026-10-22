FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY planguard ./planguard
COPY static ./static
COPY data ./data

RUN pip install --no-cache-dir . "uvicorn[standard]>=0.29"

ENV PLANGUARD_DATA_DIR=/app/data \
    PLANGUARD_DAILY_CAP_USD=2.0 \
    PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["sh", "-c", "uvicorn planguard.console:app --host 0.0.0.0 --port ${PORT:-7860}"]
