FROM python:3.12.16-slim-trixie

RUN apt-get update \
    && apt-get install -y --no-install-recommends jq ripgrep less file \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash agent

# Evidence is a read-only copy; findings go to /workspace/output.
COPY evidence/ /workspace/evidence/
RUN chmod -R a-w,a+rX /workspace/evidence \
    && mkdir -p /workspace/output && chown agent:agent /workspace/output

WORKDIR /workspace
