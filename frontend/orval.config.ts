import { defineConfig } from 'orval';

// Generates typed TanStack Query hooks from the backend's OpenAPI schema.
// Run `npm run api:generate` after the backend has produced ../backend/openapi.json.
export default defineConfig({
  store: {
    input: './openapi.json',
    output: {
      mode: 'tags-split',
      target: './src/api/generated',
      client: 'react-query',
      httpClient: 'axios',
      clean: true,
    },
  },
});
