# AkhavanLink Server — Created by Alireza Akhavan (علیرضا اخوان)
# Virtual LAN relay for gamers.   docker build -t akhavanlink-server .   docker run -p 8080:8080 akhavanlink-server
# If your host cannot pull from Docker Hub, change PY_IMAGE to a mirror of python:3.12-alpine.
ARG PY_IMAGE=python:3.12-alpine
FROM ${PY_IMAGE}

LABEL org.opencontainers.image.title="AkhavanLink Server" \
      org.opencontainers.image.description="Virtual LAN relay server for gamers" \
      org.opencontainers.image.authors="Alireza Akhavan" \
      org.opencontainers.image.vendor="Alireza Akhavan"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app
COPY akhavanlink/__init__.py akhavanlink/__init__.py
COPY akhavanlink/common akhavanlink/common
COPY akhavanlink/server akhavanlink/server

RUN adduser -D -u 10001 akhavan
USER akhavan

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-m", "akhavanlink.server", "--healthcheck"]

CMD ["python", "-m", "akhavanlink.server"]
