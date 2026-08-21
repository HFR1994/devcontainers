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