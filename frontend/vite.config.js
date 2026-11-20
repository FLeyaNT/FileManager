import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxy = {
    '/api': { target: env.FILEMANAGER_API_URL || 'http://127.0.0.1:8000' },
  };

  return {
    esbuild: { jsx: 'automatic' },
    server: { port: 5173, proxy },
    preview: { port: 5173, proxy },
  };
});
