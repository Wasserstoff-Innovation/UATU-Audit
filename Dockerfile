FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl jq graphviz ca-certificates docker.io build-essential pkg-config libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Foundry (forge/anvil)
RUN curl -L https://foundry.paradigm.xyz | bash && \
    /root/.foundry/bin/foundryup
ENV PATH="/root/.foundry/bin:${PATH}"

# Rust toolchain (cargo/rustc)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml README.md ./
COPY auditor ./auditor
COPY examples ./examples

RUN pip install --no-cache-dir hatchling && \
    python -m pip install --no-cache-dir -e .

ENTRYPOINT ["auditor"]
