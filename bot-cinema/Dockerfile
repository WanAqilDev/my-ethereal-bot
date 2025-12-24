FROM python:3.12-slim
WORKDIR /app

COPY bot-cinema/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common /app/common
COPY bot-cinema /app/bot
ENV PYTHONPATH=/app

WORKDIR /app/bot
CMD ["python", "main.py"]
