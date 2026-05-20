FROM node:20-slim

RUN npm install -g @google/gemini-cli@latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl jq ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /app/entrypoint.sh
COPY mcp-bridge.mjs /app/mcp-bridge.mjs
RUN chmod +x /app/entrypoint.sh

WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
