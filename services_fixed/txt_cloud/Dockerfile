FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TXTCLOUD_DB=/data/users.db

WORKDIR /app

RUN pip install --no-cache-dir "flask>=3.0,<4" "gunicorn>=22,<24"
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

COPY --chown=app:app app.py db.py html_build.py templates.json ./
COPY --chown=app:app static/    ./static/

RUN mkdir -p /app/storage /data \
 && chown -R app:app /app/storage /data

USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/').read()" || exit 1

CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
