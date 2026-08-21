import { startHTTPServer, proxyServer } from 'mcp-proxy';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { Server } from '@modelcontextprotocol/server';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import { pipeline } from 'node:stream/promises';
import path from 'node:path';
import os from 'node:os';

const PORT = process.env.PORT || 8080;
const TMP_ROOT = os.tmpdir();
const TMP_PREFIX = 'chrome-devtools-mcp-';
const FILES_PREFIX = '/files/';

const CHROME_ARGS = [
  '--headless=true',
  '--isolated=true',
  '--chromeArg=--no-sandbox',
  '--chromeArg=--disable-setuid-sandbox',
  '--chromeArg=--disable-dev-shm-usage',
];

const FILES_INSTRUCTIONS = `Some tools (e.g. take_screenshot, take_heapsnapshot, performance_start_trace/performance_stop_trace, lighthouse_audit) save their output to a file instead of, or in addition to, returning it inline. The reported path looks like "/tmp/chrome-devtools-mcp-<id>/<filename>".

Call the "read_temp_file" tool with that exact path to retrieve it. Small text/JSON/image files are returned inline; large or other binary files instead come back with a "GET /files/chrome-devtools-mcp-<id>/<filename>" URL — fetch that from this same MCP server's host and port (Range requests are supported for large files). Only files inside a "chrome-devtools-mcp-<id>" temp directory are accessible this way.`;

const MIME = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.json': 'application/json', '.gz': 'application/gzip',
  '.webm': 'video/webm', '.mp4': 'video/mp4', '.heapsnapshot': 'application/json',
  '.txt': 'text/plain', '.network-request': 'text/plain', '.network-response': 'text/plain',
};

const READ_FILE_TOOL_NAME = 'read_temp_file';
const READ_FILE_TOOL = {
  name: READ_FILE_TOOL_NAME,
  description: 'Reads a file that another chrome-devtools-mcp tool saved to its temp directory (paths reported like "/tmp/chrome-devtools-mcp-<id>/<filename>", e.g. by take_screenshot, take_heapsnapshot, performance_start_trace/performance_stop_trace, lighthouse_audit). Small text, JSON, and image files are returned inline; large or other binary files come back with an HTTP URL to fetch instead.',
  inputSchema: {
    type: 'object',
    properties: {
      path: {
        type: 'string',
        description: 'The absolute file path exactly as reported by the tool call that created it, e.g. "/tmp/chrome-devtools-mcp-P6eYfP/report.json".',
      },
    },
    required: ['path'],
  },
};
const INLINE_LIMIT_BYTES = 1_000_000;

// Shared by the /files/ HTTP route (relative paths under TMP_ROOT) and the
// read_temp_file tool (absolute paths as reported by other tool results).
function resolveSafeTempPath(candidate) {
  const resolved = path.isAbsolute(candidate) ? path.resolve(candidate) : path.resolve(TMP_ROOT, candidate);
  const relToRoot = path.relative(TMP_ROOT, resolved);
  if (relToRoot.startsWith('..') || path.isAbsolute(relToRoot)) return null;
  if (!relToRoot.split(path.sep)[0].startsWith(TMP_PREFIX)) return null;
  return resolved;
}

function safeResolve(urlPath) {
  const rel = decodeURIComponent(urlPath.slice(FILES_PREFIX.length));
  return resolveSafeTempPath(rel);
}

async function readTempFileTool(args) {
  const requestedPath = args?.path;
  if (typeof requestedPath !== 'string' || !requestedPath) {
    return { isError: true, content: [{ type: 'text', text: 'Missing required "path" argument.' }] };
  }

  const filePath = resolveSafeTempPath(requestedPath);
  if (!filePath) {
    return { isError: true, content: [{ type: 'text', text: `"${requestedPath}" is not inside a chrome-devtools-mcp temp directory.` }] };
  }

  let stat;
  try {
    stat = await fsp.stat(filePath);
  } catch {
    return { isError: true, content: [{ type: 'text', text: `No such file: ${requestedPath}` }] };
  }
  if (!stat.isFile()) {
    return { isError: true, content: [{ type: 'text', text: `Not a file: ${requestedPath}` }] };
  }

  const contentType = MIME[path.extname(filePath)] || 'application/octet-stream';

  if (stat.size <= INLINE_LIMIT_BYTES) {
    if (contentType.startsWith('image/')) {
      const data = await fsp.readFile(filePath);
      return { content: [{ type: 'image', mimeType: contentType, data: data.toString('base64') }] };
    }
    if (contentType === 'application/json' || contentType.startsWith('text/')) {
      const text = await fsp.readFile(filePath, 'utf8');
      return { content: [{ type: 'text', text }] };
    }
  }

  const relUrl = path.relative(TMP_ROOT, filePath).split(path.sep).join('/');
  return {
    content: [{
      type: 'text',
      text: `File is ${stat.size} bytes (${contentType}), too large or binary to return inline. Fetch it with GET ${FILES_PREFIX}${relUrl} on this MCP server's host/port (Range requests supported).`,
    }],
  };
}

async function serveFile(req, res) {
  const filePath = safeResolve(new URL(req.url, 'http://localhost').pathname);
  if (!filePath) return res.writeHead(403).end('Forbidden');

  let stat;
  try {
    stat = await fsp.stat(filePath);
  } catch {
    return res.writeHead(404).end('Not found');
  }
  if (!stat.isFile()) return res.writeHead(404).end('Not found');

  const contentType = MIME[path.extname(filePath)] || 'application/octet-stream';
  const range = req.headers.range;

  try {
    if (range) {
      const [startStr, endStr] = range.replace(/bytes=/, '').split('-');
      const start = parseInt(startStr, 10);
      const end = endStr ? parseInt(endStr, 10) : stat.size - 1;
      res.writeHead(206, {
        'content-range': `bytes ${start}-${end}/${stat.size}`,
        'accept-ranges': 'bytes',
        'content-length': end - start + 1,
        'content-type': contentType,
      });
      await pipeline(fs.createReadStream(filePath, { start, end }), res);
    } else {
      res.writeHead(200, { 'content-type': contentType, 'content-length': stat.size });
      await pipeline(fs.createReadStream(filePath), res);
    }
  } catch (err) {
    // Client disconnected mid-stream: pipeline() aborts without calling
    // res.end(), which leaves res.writableEnded false. mcp-proxy uses that
    // flag to decide whether onUnhandledRequest already answered the
    // request, so an un-ended response here makes it try to write its own
    // fallback reply on top of ours and crash the process.
    if (!res.writableEnded) res.end();
    if (err.code !== 'ERR_STREAM_PREMATURE_CLOSE') console.error('serveFile stream error:', err);
  }
}

async function main() {
  const stdioTransport = new StdioClientTransport({
    command: 'chrome-devtools-mcp',
    args: CHROME_ARGS,
  });

  const stdioClient = new Client(
    { name: 'chrome-devtools-mcp-http-proxy', version: '1.0.0' },
    { capabilities: {} },
  );
  await stdioClient.connect(stdioTransport);

  const serverVersion = stdioClient.getServerVersion();
  const serverCapabilities = stdioClient.getServerCapabilities();

  await startHTTPServer({
    port: PORT,
    cors: true,
    createServer: async () => {
      try {
        const upstreamInstructions = stdioClient.getInstructions();
        const instructions = [upstreamInstructions, FILES_INSTRUCTIONS].filter(Boolean).join('\n\n');
        const mcpServer = new Server(serverVersion, { capabilities: serverCapabilities, instructions });
        await proxyServer({ client: stdioClient, server: mcpServer, serverCapabilities });

        if (serverCapabilities?.tools) {
          mcpServer.setRequestHandler('tools/list', async (request, ctx) => {
            const upstream = await stdioClient.listTools(request.params, { signal: ctx.mcpReq.signal });
            // Only append on the first page so a paginated listing doesn't repeat it.
            if (request.params?.cursor) return upstream;
            return { ...upstream, tools: [...upstream.tools, READ_FILE_TOOL] };
          });
          mcpServer.setRequestHandler('tools/call', async (request, ctx) => {
            if (request.params.name === READ_FILE_TOOL_NAME) {
              return readTempFileTool(request.params.arguments);
            }
            return stdioClient.callTool(request.params, { signal: ctx.mcpReq.signal });
          });
        }

        return mcpServer;
      } catch (err) {
        console.error('createServer failed:', err);
        throw err;
      }
    },
    onUnhandledRequest: async (req, res) => {
      if (req.method === 'GET' && req.url === '/ping') {
        return res.writeHead(200, { 'content-type': 'text/plain' }).end('pong');
      }
      if (req.method === 'GET' && req.url.startsWith(FILES_PREFIX)) {
        return serveFile(req, res);
      }
      res.writeHead(404).end('Not found');
    },
  });

  console.log(`chrome-devtools-mcp HTTP proxy + file server listening on :${PORT}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});