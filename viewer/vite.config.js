import { defineConfig } from 'vite'

export default defineConfig({
    server: {
        proxy: {
            '/api/volume': { target: 'http://127.0.0.1:8000', changeOrigin: true },
            '/api/ml': { target: 'http://127.0.0.1:8001', changeOrigin: true }
        }
    }
})
