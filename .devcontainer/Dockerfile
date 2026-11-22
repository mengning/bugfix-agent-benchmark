FROM docker:28-cli AS docker-cli
FROM python:3.12-slim-bookworm

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git openssh-server sudo \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir 'datasets>=2.14' 'swebench==4.1.0'
