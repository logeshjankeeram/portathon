FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY . /app

# Optional system deps
# RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip
# Try project requirements if present
RUN if [ -f mana/requirements.txt ]; then pip install -r mana/requirements.txt; fi
# Ensure core runtime deps
RUN pip install fastapi uvicorn[standard] pandas

ENV PYTHONPATH=/app/mana/src:/app/mana:/app
ENV PORT=${PORT}
CMD ["/bin/sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
