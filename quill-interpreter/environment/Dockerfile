FROM python:3.12.16-slim-trixie

# A C/C++ toolchain so the interpreter can be written in a compiled language if the agent prefers.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ make libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash agent

COPY workspace/ /workspace/
RUN chmod 755 /workspace/quill/run_examples.sh && chown -R agent:agent /workspace

WORKDIR /workspace
