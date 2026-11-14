FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
COPY requirements-dev.txt ./
COPY pyproject.toml ./
COPY tests ./tests
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]