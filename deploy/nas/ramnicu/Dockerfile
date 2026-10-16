FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates poppler-utils && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
ARG SOURCE_ROOT=.
COPY ${SOURCE_ROOT}/administratie /app/administratie
RUN mkdir -p /data && chown 1000:1000 /data
USER 1000:1000
ENTRYPOINT ["python", "-m", "administratie.ramnicu_valcea.collector"]
CMD ["--data-dir", "/data/ramnicu-valcea"]
