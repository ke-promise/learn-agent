import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置保持尽量精简，只保留当前项目需要的 Vue 插件和开发端口。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
})