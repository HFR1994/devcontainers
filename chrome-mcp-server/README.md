# chrome-devtools-mcp in Docker

Run [chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) inside a container, with headless Chrome bundled alongside it.

> **Note:** There is no official Docker image for this project. This setup was derived from the project's CLI flags and Puppeteer's containerization requirements — not from an upstream Dockerfile.

## How it works

`chrome-devtools-mcp` is a Node.js MCP server that uses Puppeteer to either launch a new Chrome instance or attach to an existing one, then exposes DevTools capabilities (network inspection, performance tracing, console, accessibility snapshots, input automation, etc.) as MCP tools. It communicates with MCP clients over **stdio**, not a network port.

Because containers don't grant the kernel privileges (`CAP_SYS_ADMIN`) Chrome's sandbox needs by default, and have no display, the container build launches Chrome **headless** with **`--no-sandbox`**.

## Requirements

- Node.js `^20.19.0`, `^22.12.0`, or `>=23`
- Docker

## Dockerfile

```dockerfile
FROM node:22-slim

# Chrome's runtime deps (standard headless-Chrome-on-Debian list)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 \
    libglib2.0-0 libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 xdg-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the MCP server
RUN npm install -g chrome-devtools-mcp@latest

# Download a Chrome binary via Puppeteer's installer
RUN npx --yes puppeteer browsers install chrome

# Run as non-root (Chrome refuses --no-sandbox as root without extra flags)
RUN useradd -m mcpuser
USER mcpuser

ENTRYPOINT ["chrome-devtools-mcp", "--headless=true", "--isolated=true", \
  "--chromeArg=--no-sandbox", "--chromeArg=--disable-setuid-sandbox", \
  "--chromeArg=--disable-dev-shm-usage"]
```

## Build

```bash
docker build -t chrome-devtools-mcp .
```

## Run standalone (sanity check)

```bash
docker run -i --rm --init chrome-devtools-mcp
```

The process expects an MCP client speaking stdio JSON-RPC on the other end; it won't produce visible output on its own.

## MCP client configuration

Point your MCP client at `docker run` instead of the local binary:

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--init", "chrome-devtools-mcp"]
    }
  }
}
```

## Flags explained

| Flag | Why |
|---|---|
| `--headless=true` | No display available in the container |
| `--isolated=true` | Fresh, throwaway Chrome profile per run — avoids stale-profile conflicts |
| `--chromeArg=--no-sandbox` | Chrome's sandbox needs `CAP_SYS_ADMIN`, which containers don't grant by default |
| `--chromeArg=--disable-setuid-sandbox` | Companion flag to `--no-sandbox` on Linux |
| `--chromeArg=--disable-dev-shm-usage` | Docker's default `/dev/shm` (64MB) is too small for Chrome and causes crashes |

## Alternative: connect to Chrome running outside the container

If you'd rather not run Chrome sandboxed-off inside the container, start Chrome on the host (or another container) with remote debugging enabled, and point the MCP server at it instead of having it launch Chrome itself:

```bash
# On the host
google-chrome --headless --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-profile
```

```bash
# MCP server container, connecting out instead of launching its own Chrome
docker run -i --rm --network host chrome-devtools-mcp \
  --browserUrl http://127.0.0.1:9222
```

This avoids sandbox flag tradeoffs entirely, at the cost of managing Chrome's lifecycle separately from the MCP server's.

## Improving sandbox security (optional)

If your container orchestrator permits it, you can grant the capability Chrome's sandbox needs instead of disabling it:

```bash
docker run -i --rm --init --cap-add=SYS_ADMIN chrome-devtools-mcp
```

Then drop `--chromeArg=--no-sandbox --chromeArg=--disable-setuid-sandbox` from the entrypoint.

## Troubleshooting

- **Chrome crashes immediately / `SIGTRAP`**: usually the `/dev/shm` size issue — confirm `--disable-dev-shm-usage` is set, or mount a bigger shm: `docker run --shm-size=1gb ...`.
- **"Running as root without --no-sandbox is not supported"**: either run as a non-root user (as in the Dockerfile above) or add `--no-sandbox`.
- **MCP client hangs with no response**: confirm you're running with `-i` (interactive/stdin open) — without it, stdio-based MCP transport can't communicate.