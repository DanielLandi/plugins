import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: { alias: { '@mv/kit': fileURLToPath(new URL('./kit', import.meta.url)) } },
  test: { include: ['kit/**/*.test.ts', 'tools/**/*.test.ts'], environment: 'node' },
});
