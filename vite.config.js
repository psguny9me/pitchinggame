import { defineConfig } from 'vite'

export default defineConfig({
    base: './', // Ensures assets are loaded correctly on GitHub Pages and local builds
    build: {
        outDir: 'dist',
    },
    server: {
        host: true
    }
})
