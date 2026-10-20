import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  root: resolve(__dirname, '../public_demo_src'),
  base: '/NeuroVista/',
  plugins: [react()],
  resolve: { alias: {
    react: resolve(__dirname, 'node_modules/react'),
    'react-dom': resolve(__dirname, 'node_modules/react-dom'),
    three: resolve(__dirname, 'node_modules/three'),
    '@react-three/fiber': resolve(__dirname, 'node_modules/@react-three/fiber'),
    '@react-three/drei': resolve(__dirname, 'node_modules/@react-three/drei'),
  } },
  build: { outDir: resolve(__dirname, '../public_demo_dist'), emptyOutDir: true },
})
