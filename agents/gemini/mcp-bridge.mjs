#!/usr/bin/env node
/**
 * Stdio-to-HTTP MCP Bridge
 *
 * Gemini CLI talks to this via stdio MCP protocol.
 * This bridge forwards JSON-RPC requests to the DeepSecure gateway's /mcp HTTP endpoint.
 *
 * Required env vars:
 *   GATEWAY_URL  — e.g. https://app.deepsecure.one/mcp
 *   AGENT_JWT    — Bearer token for Authorization header
 */

import { createInterface } from "readline";

const GATEWAY_URL = process.env.GATEWAY_URL || process.env.DEEPSECURE_GATEWAY_URL;
const AGENT_JWT = process.env.AGENT_JWT;

if (!GATEWAY_URL || !AGENT_JWT) {
  process.stderr.write(
    "ERROR: mcp-bridge requires GATEWAY_URL and AGENT_JWT env vars\n"
  );
  process.exit(1);
}

let sessionInitialized = false;

async function forwardToGateway(request) {
  const resp = await fetch(GATEWAY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${AGENT_JWT}`,
    },
    body: JSON.stringify(request),
  });

  if (!resp.ok) {
    const text = await resp.text();
    process.stderr.write(
      `Gateway HTTP ${resp.status}: ${text.slice(0, 200)}\n`
    );
    return {
      jsonrpc: "2.0",
      id: request.id,
      error: { code: -32000, message: `Gateway error: ${resp.status}`, data: text.slice(0, 500) },
    };
  }

  return resp.json();
}

async function handleRequest(request) {
  const { method, id } = request;

  if (method === "initialize") {
    const gwResponse = await forwardToGateway(request);
    if (gwResponse.result) {
      sessionInitialized = true;
    }
    return gwResponse;
  }

  if (method === "notifications/initialized") {
    return null;
  }

  if (!sessionInitialized && (method === "tools/list" || method === "tools/call")) {
    const initReq = {
      jsonrpc: "2.0",
      method: "initialize",
      id: 0,
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "mcp-bridge", version: "1.0.0" },
      },
    };
    const initResp = await forwardToGateway(initReq);
    if (initResp.result) {
      sessionInitialized = true;
    }
  }

  return forwardToGateway(request);
}

const rl = createInterface({ input: process.stdin });

rl.on("line", async (line) => {
  if (!line.trim()) return;

  let request;
  try {
    request = JSON.parse(line);
  } catch {
    process.stderr.write(`Invalid JSON: ${line.slice(0, 100)}\n`);
    return;
  }

  try {
    const response = await handleRequest(request);
    if (response !== null) {
      process.stdout.write(JSON.stringify(response) + "\n");
    }
  } catch (err) {
    process.stderr.write(`Bridge error: ${err.message}\n`);
    if (request.id !== undefined) {
      const errResp = {
        jsonrpc: "2.0",
        id: request.id,
        error: { code: -32603, message: err.message },
      };
      process.stdout.write(JSON.stringify(errResp) + "\n");
    }
  }
});

rl.on("close", () => process.exit(0));

process.stderr.write("[mcp-bridge] Started. Gateway: " + GATEWAY_URL + "\n");
