FROM python:3.12.16-slim-trixie

# A C/C++ toolchain in case the agent prefers a compiled language.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ make libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash agent

COPY workspace/ /workspace/
RUN chmod 755 /workspace/iam/check_example.sh && chown -R agent:agent /workspace

WORKDIR /workspace
