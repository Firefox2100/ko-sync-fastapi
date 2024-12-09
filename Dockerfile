FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DATA_PATH /data

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY ./src/ /app/
COPY ./docker-entry.sh /app/docker-entry.sh

EXPOSE 8000

VOLUME ["/data"]

ENTRYPOINT ["bash", "/app/docker-entry.sh"]
