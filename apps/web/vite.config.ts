import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    host: true,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },

  build: {
    // Output directory
    outDir: 'dist',

    // Generate sourcemaps for production debugging (set to false for smaller bundle)
    sourcemap: false,

    // Chunk size warning limit (500kb)
    chunkSizeWarningLimit: 500,

    // Rollup options for optimization
    rollupOptions: {
      output: {
        // Manual chunk splitting for better caching
        manualChunks: {
          // Vendor chunk for React and core libraries
          'react-vendor': ['react', 'react-dom'],

          // UI libraries chunk
          'ui-vendor': ['lucide-react', 'recharts'],

          // Data fetching chunk
          'data-vendor': ['@tanstack/react-query', 'axios'],
        },

        // Asset file naming
        assetFileNames: 'assets/[name]-[hash][extname]',

        // Chunk file naming
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',
      },
    },

    // Minification options
    minify: 'esbuild',

    // Target modern browsers for smaller output
    target: 'es2020',

    // CSS code splitting
    cssCodeSplit: true,
  },

  // Optimization options
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'axios',
      '@tanstack/react-query',
      'lucide-react',
      'recharts'
    ],
  },

  // Resolve aliases for cleaner imports
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@api': path.resolve(__dirname, './src/api'),
      '@types': path.resolve(__dirname, './src/types'),
    },
  },

  // Preview server config (for testing production builds)
  preview: {
    port: 5173,
    host: true,
  },
})
