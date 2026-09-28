FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    default-mysql-client \
    gcc \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app/ /app/

RUN pybabel compile -d /app/translations

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "60", "main:app"]
