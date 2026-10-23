FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml ./
RUN mkdir shop && touch shop/__init__.py && pip install . && rm -rf shop build

COPY shop ./shop
RUN pip install --no-deps .

RUN useradd --create-home --uid 10001 shop
USER shop

ENTRYPOINT ["python", "-m", "shop"]
