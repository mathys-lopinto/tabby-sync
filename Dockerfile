# syntax=docker/dockerfile:1.7

############################
# Stage 1: build wheels
############################
FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN pip install poetry==2.3.4 poetry-plugin-export==1.10.0

WORKDIR /build
COPY backend/pyproject.toml backend/poetry.lock ./

# Export the locked deps and install them into a relocatable venv.
RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && poetry export --only main --without-hashes -f requirements.txt -o requirements.txt \
    && /venv/bin/pip install -r requirements.txt


############################
# Stage 2: runtime
############################
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH" \
    PORT=80

COPY --from=builder /venv /venv

WORKDIR /app
COPY backend/ /app/

RUN chmod +x /app/start.sh /app/manage.sh \
    && /venv/bin/python manage.py collectstatic --noinput || true

EXPOSE 80
CMD ["/app/start.sh"]
