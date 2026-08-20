FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir django uvicorn psycopg[binary] python-dotenv

COPY . .

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
