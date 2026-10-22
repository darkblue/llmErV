FROM python:3.12-slim
RUN --mount=type=secret,id=cloud_ca,target=/run/secrets/cloud_ca,required=false if [ -f /run/secrets/cloud_ca ]; then cp /run/secrets/cloud_ca /usr/local/share/ca-certificates/cloud-proxy.crt && update-ca-certificates; fi
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements-dev.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-dev.txt
COPY --chown=1000:1000 backend backend
COPY --chown=1000:1000 tests tests
RUN useradd --uid 1000 --create-home app && mkdir /app/data && chown app:app /app/data
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000"]
