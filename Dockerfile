# Lightweight Python runtime for the FastAPI application.
FROM python:3.13-slim

WORKDIR /app

# Install pinned production dependencies first, in their own layer, so that
# an application code change does not invalidate the (slow) dependency
# install. This layer only changes when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the package definition and application source and install the
# local package itself. --no-deps avoids re-resolving/re-downloading the
# dependencies already installed above. `pip check` then fails the build if
# requirements.txt has drifted from pyproject.toml (a dependency declared
# there but missing or incompatible in the pinned lock).
COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir --no-deps . && pip check

# Runtime files required by the application and Alembic.
COPY migrations ./migrations
COPY alembic.ini .
COPY main.py .

# Run as a non-root user.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3).status == 200 else 1)"]

# Production containers run without development auto-reload. The loop
# factory is required on Windows for psycopg's async mode and is harmless
# (identical to the default loop) on Linux; see app/core/event_loop.py.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "app.core.event_loop:loop_factory"]
