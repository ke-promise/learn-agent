<template>
  <div class="chart-grid">
    <div class="chart-card">
      <div class="chart-title">系统指标概览</div>
      <div ref="overviewRef" class="chart-canvas"></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">最近一次任务 Trace</div>
      <div ref="traceRef" class="chart-canvas"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

import type { ChatResponse, OverviewResponse } from '../types'

const props = defineProps<{
  overview: OverviewResponse | null
  lastChat: ChatResponse | null
}>()

const overviewRef = ref<HTMLDivElement | null>(null)
const traceRef = ref<HTMLDivElement | null>(null)
let overviewChart: echarts.ECharts | null = null
let traceChart: echarts.ECharts | null = null

function metricToNumber(value: string): number {
  const matched = value.match(/[\d.]+/)
  return matched ? Number(matched[0]) : 0
}

function renderCharts() {
  // 左图：系统概览指标，展示 RAG 命中率、平均 Agent 调用等全局指标。
  if (overviewRef.value) {
    overviewChart ??= echarts.init(overviewRef.value)
    const metrics = props.overview?.metrics ?? []
    overviewChart.setOption({
      tooltip: {},
      xAxis: {
        type: 'category',
        data: metrics.map((item) => item.label),
        axisLabel: { color: '#6e5a45' },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#6e5a45' },
      },
      series: [
        {
          type: 'bar',
          data: metrics.map((item) => metricToNumber(item.value)),
          itemStyle: {
            color: '#b86e3c',
            borderRadius: [8, 8, 0, 0],
          },
        },
      ],
      grid: { left: 30, right: 16, top: 24, bottom: 32 },
    })
  }

  // 右图：最近一次任务每个节点的耗时，帮助理解编排链路和性能分布。
  if (traceRef.value) {
    traceChart ??= echarts.init(traceRef.value)
    const trace = props.lastChat?.trace ?? []
    traceChart.setOption({
      tooltip: {},
      xAxis: {
        type: 'category',
        data: trace.map((item) => `${item.agent_name}:${item.step_name}`),
        axisLabel: { color: '#6e5a45', rotate: 20 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#6e5a45' },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          data: trace.map((item) => item.duration_ms),
          lineStyle: { color: '#577762', width: 3 },
          itemStyle: { color: '#577762' },
          areaStyle: { color: 'rgba(87, 119, 98, 0.18)' },
        },
      ],
      grid: { left: 30, right: 16, top: 24, bottom: 48 },
    })
  }
}

function handleResize() {
  overviewChart?.resize()
  traceChart?.resize()
}

onMounted(() => {
  renderCharts()
  window.addEventListener('resize', handleResize)
})

watch(
  () => [props.overview, props.lastChat],
  () => renderCharts(),
  { deep: true },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  overviewChart?.dispose()
  traceChart?.dispose()
})
</script>