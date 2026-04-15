FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
ARG GIT_TOKEN
RUN git config --global url."https://oauth2:${GIT_TOKEN}@git.eifer.kit.edu/".insteadOf "https://git.eifer.kit.edu/" \
    && pip install --no-cache-dir -r requirements.txt \
    && git config --global --remove-section url."https://oauth2:${GIT_TOKEN}@git.eifer.kit.edu/"

COPY app ./app
COPY worker.py ./worker.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
