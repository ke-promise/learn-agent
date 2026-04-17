import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import './styles.css'

// 前端应用启动入口：注册状态管理、UI 组件库和全局样式。
createApp(App).use(createPinia()).use(ElementPlus).mount('#app')