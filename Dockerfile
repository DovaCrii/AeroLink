FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir fastapi 'uvicorn[standard]' pydantic-settings

EXPOSE 8000
CMD ["uvicorn", "aerolink.main:app", "--host", "0.0.0.0", "--port", "8000"]

