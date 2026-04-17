import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '../api'
import type { ChatResponse, MemoryRecord, OverviewResponse } from '../types'


export const useDashboardStore = defineStore('dashboard', () => {
  // 首页概览、最近一次对话结果、当前用户记忆是工作台最核心的三段状态。
  const overview = ref<OverviewResponse | null>(null)
  const lastChat = ref<ChatResponse | null>(null)
  const userMemories = ref<MemoryRecord[]>([])

  async function loadOverview() {
    const { data } = await api.get<OverviewResponse>('/overview')
    overview.value = data
    return data
  }

  async function loadMemories(userId: string) {
    const { data } = await api.get<{ items: MemoryRecord[] }>(`/memories/${userId}`)
    userMemories.value = data.items
    return data.items
  }

  async function sendMessage(payload: { user_id: string; conversation_id: string; message: string }) {
    const { data } = await api.post<ChatResponse>('/chat', payload)
    lastChat.value = data

    // 任务执行完成后，首页统计和用户记忆都可能变化，因此顺手刷新。
    await loadOverview()
    await loadMemories(payload.user_id)
    return data
  }

  async function uploadDocument(formData: FormData) {
    await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    await loadOverview()
  }

  async function createMemory(payload: {
    user_id: string
    namespace: string
    memory_type: 'profile' | 'episodic' | 'semantic'
    content: string
    importance: number
  }) {
    await api.post('/memories', payload)
    await loadOverview()
    await loadMemories(payload.user_id)
  }

  async function loadIncidentDemo(userId: string) {
    // 这组 Demo 数据围绕“支付系统故障复盘”主场景构造，便于一键演示整条链路。
    const demoDocuments = [
      {
        title: '支付系统事故复盘：回调超时',
        source: 'incident-postmortem',
        content:
          '支付系统在 4 月流量高峰期间出现回调超时。根因是连接池过小叠加重试风暴，导致 worker 饱和。行动项包括扩容连接池、限制重试和增加告警。',
      },
      {
        title: '项目 Alpha 风险周报',
        source: 'weekly-report',
        content:
          'Alpha 项目当前的主要风险集中在支付和订单链路，支付模块存在高优先级未关闭工单，需要重点向管理层说明影响范围和缓解计划。',
      },
      {
        title: '支付系统限流策略说明',
        source: 'runbook',
        content:
          '支付系统采用分级限流。高峰期优先保证回调链路，必要时对非核心查询接口进行降级，并要求在故障复盘中同步记录限流阈值与回滚条件。',
      },
    ]

    for (const item of demoDocuments) {
      const formData = new FormData()
      formData.append('title', item.title)
      formData.append('source', item.source)
      formData.append('content', item.content)
      await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    }

    await api.post('/memories', {
      user_id: userId,
      namespace: 'default',
      memory_type: 'profile',
      content: '我负责支付系统，汇报时喜欢先结论后依据。',
      importance: 0.9,
    })

    await loadOverview()
    await loadMemories(userId)
    return sendMessage({
      user_id: userId,
      conversation_id: 'demo-incident',
      message: '帮我总结支付系统最近故障，并给老板写一份汇报',
    })
  }

  return {
    overview,
    lastChat,
    userMemories,
    loadOverview,
    loadMemories,
    sendMessage,
    uploadDocument,
    createMemory,
    loadIncidentDemo,
  }
})