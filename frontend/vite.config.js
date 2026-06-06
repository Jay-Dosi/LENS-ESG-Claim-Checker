import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  // Production preview server (used by Code Engine / IBM Cloud deployment)
  preview: {
    port: parseInt(process.env.PORT) || 8080,
    host: '0.0.0.0',
    allowedHosts: 'all',
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  }
})

// Made with Bob
