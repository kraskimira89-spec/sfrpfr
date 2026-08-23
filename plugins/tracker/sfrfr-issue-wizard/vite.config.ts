import fs from 'fs';
import type { IncomingMessage, ServerResponse } from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

import react from '@vitejs/plugin-react';
import type { ViteDevServer } from 'vite';
import { defineConfig } from 'vite';
import svgr from 'vite-plugin-svgr';

import { proxyPlugin } from './proxy';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(() => {
    return {
        base: './',
        server: {
            port: 5173,
            strictPort: true,
            cors: true,
            headers: {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
                'Access-Control-Allow-Headers': 'X-Requested-With, content-type, Authorization',
                'Content-Security-Policy':
                    "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src data: blob: *; font-src 'self' data:; media-src 'self' blob:; connect-src 'self'; form-action 'self'; frame-src 'none'; base-uri 'none'; object-src 'none'; worker-src 'self' blob:; manifest-src 'none'",
            },
        },
        plugins: [
            svgr(),
            react(),
            {
                name: 'serve-config-from-root',
                apply: 'serve',
                configureServer(server: ViteDevServer) {
                    server.middlewares.use(
                        (req: IncomingMessage, res: ServerResponse, next: () => void) => {
                            if (req.url === '/config.json') {
                                const configPath = path.resolve(__dirname, 'config.json');
                                if (fs.existsSync(configPath)) {
                                    res.setHeader('Content-Type', 'application/json');
                                    res.setHeader('Access-Control-Allow-Origin', '*');
                                    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
                                    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
                                    res.end(fs.readFileSync(configPath, 'utf-8'));
                                    return;
                                }
                            }
                            next();
                        },
                    );
                },
            },
            proxyPlugin(),
        ],
        build: {
            sourcemap: false,
            cssCodeSplit: true,
            rollupOptions: {
                output: {
                    sourcemapIgnoreList: () => false,
                },
            },
        },
        css: {
            devSourcemap: true,
            preprocessorOptions: {
                scss: {},
            },
        },
    };
});
