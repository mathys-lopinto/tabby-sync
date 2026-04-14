# syntax=docker/dockerfile:1.7

############################
# Stage 1 — build wheels
############################
FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==1.8.3

WORKDIR /build
COPY backend/pyproject.toml ./

# Export locked deps then install into an isolated venv we'll copy over.
RUN poetry lock --no-update || poetry lock
RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && poetry export -f requirements.txt --without-hashes -o requirements.txt \
    && /venv/bin/pip install -r requirements.txt


############################
# Stage 2 — runtime
############################
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH" \
    PORT=80

RUN apt-get update && apt-get install -y --no-install-recommends \
        libmariadb3 \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# dockerize — used by start.sh to wait for the DB
ARG DOCKERIZE_VERSION=v0.9.3
RUN wget -qO- \
      "https://github.com/powerman/dockerize/releases/download/${DOCKERIZE_VERSION}/dockerize-linux-amd64-${DOCKERIZE_VERSION}.tar.gz" \
    | tar -xz -C /usr/local/bin

COPY --from=builder /venv /venv

WORKDIR /app
COPY backend/ /app/

RUN chmod +x /app/start.sh /app/manage.sh \
    && /venv/bin/python manage.py collectstatic --noinput || true

EXPOSE 80
CMD ["/app/start.sh"]
