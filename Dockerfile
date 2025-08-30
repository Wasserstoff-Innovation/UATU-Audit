FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl jq graphviz ca-certificates docker.io build-essential pkg-config libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Foundry
RUN curl -L https://foundry.paradigm.xyz | bash && /root/.foundry/bin/foundryup
ENV PATH="/root/.foundry/bin:${PATH}"

# Rust + wasm target (+ optional CLI)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y && \
    /root/.cargo/bin/rustup target add wasm32-unknown-unknown || true
# Optional: CLI (ignore failure to keep build deterministic)
RUN /root/.cargo/bin/cargo install --locked soroban-cli || true
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml README.md ./
COPY auditor ./auditor
COPY examples ./examples

RUN pip install --no-cache-dir hatchling && \
    python -m pip install --no-cache-dir -e .

ENTRYPOINT ["auditor"]
