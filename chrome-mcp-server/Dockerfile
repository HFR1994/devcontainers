FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg \
    && curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json src/proxy.mjs /app/
RUN npm install --omit=dev

ENV PATH="/app/node_modules/.bin:${PATH}"

RUN useradd -m mcpuser && chown -R mcpuser /app
USER mcpuser

EXPOSE 8080

ENTRYPOINT ["node", "/app/proxy.mjs"]