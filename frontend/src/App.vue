<template>
  <div class="page-shell">
    <aside class="sidebar-panel">
      <div class="hero-block">
        <div class="eyebrow">Incident Review Copilot</div>
        <h1>故障复盘与汇报助手</h1>
        <p>
          围绕“故障复盘与汇报”主场景，统一展示知识引用、Memory 命中、工具结果、Agent Trace 与系统指标。
        </p>
      </div>

      <section class="panel-section">
        <div class="section-title">系统概览</div>
        <div class="card-grid compact-grid">
          <article v-for="card in overview?.cards ?? []" :key="card.label" class="stat-card">
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-value">{{ card.value }}</div>
          </article>
        </div>
      </section>

      <section class="panel-section">
        <div class="section-title">运行指标</div>
        <div class="metric-list">
          <article v-for="metric in overview?.metrics ?? []" :key="metric.label" class="metric-card">
            <div class="metric-top">
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
            </div>
            <p>{{ metric.hint }}</p>
          </article>
        </div>
      </section>

      <!-- 图表区域：把全局指标和单次 Trace 的信息单独图形化展示。 -->
      <InsightCharts :overview="overview" :last-chat="lastChat" />
    </aside>

    <main class="main-panel">
      <header class="topbar">
        <div>
          <div class="section-title">任务工作台</div>
          <p class="muted">让功能区更清楚地区分为准备数据、发起任务、查看结果和核对依据。</p>
        </div>
        <div class="quick-actions">
          <button class="ghost-button" @click="loadDemo">加载真实业务 Demo</button>
          <button class="ghost-button" @click="setPrompt('帮我总结支付系统最近故障，并给老板写一份汇报')">示例问题</button>
        </div>
      </header>

      <!-- 三个 tab 对应项目里的三类常见操作：发任务、管知识、管记忆。 -->
      <nav class="tab-row">
        <button :class="['tab-button', { active: activeTab === 'workbench' }]" @click="activeTab = 'workbench'">任务工作台</button>
        <button :class="['tab-button', { active: activeTab === 'knowledge' }]" @click="activeTab = 'knowledge'">知识库管理</button>
        <button :class="['tab-button', { active: activeTab === 'memory' }]" @click="activeTab = 'memory'">Memory 管理</button>
      </nav>

      <section v-if="activeTab === 'workbench'" class="content-grid">
        <article class="surface-card wide-card">
          <div class="section-title">任务输入</div>
          <div class="form-grid two-col">
            <label>
              <span>用户 ID</span>
              <input v-model="userId" placeholder="例如：alice" />
            </label>
            <label>
              <span>会话 ID</span>
              <input v-model="conversationId" placeholder="例如：incident-room-1" />
            </label>
          </div>
          <label>
            <span>任务描述</span>
            <textarea v-model="prompt" rows="6" placeholder="输入你的问题，例如：帮我总结支付系统最近故障，并给老板写一份汇报"></textarea>
          </label>
          <div class="quick-chip-row">
            <button class="chip-button" @click="setPrompt('帮我分析支付系统最近故障趋势')">状态分析</button>
            <button class="chip-button" @click="setPrompt('支付系统的限流策略是什么？')">知识查询</button>
            <button class="chip-button" @click="setPrompt('记住：我负责支付系统，输出时先结论后原因')">偏好管理</button>
          </div>
          <div class="action-row">
            <button class="primary-button" :disabled="sending" @click="sendPrompt">
              {{ sending ? '执行中...' : '发起任务' }}
            </button>
          </div>
        </article>

        <article class="surface-card">
          <div class="section-title">任务摘要</div>
          <div v-if="lastChat" class="summary-stack">
            <div class="summary-item">
              <span>用户意图</span>
              <strong>{{ lastChat.intent_label }}</strong>
            </div>
            <div class="summary-item">
              <span>RAG 命中</span>
              <strong>{{ lastChat.metrics.rag_hit ? '是' : '否' }}</strong>
            </div>
            <div class="summary-item">
              <span>总耗时</span>
              <strong>{{ lastChat.metrics.latency_ms }} ms</strong>
            </div>
            <div class="summary-item">
              <span>Agent 调用</span>
              <strong>{{ lastChat.metrics.agent_call_count }}</strong>
            </div>
          </div>
          <div v-else class="empty-state">任务执行后，这里会展示意图、耗时和调用次数。</div>
        </article>

        <article class="surface-card wide-card">
          <div class="section-title">结果输出（Markdown）</div>
          <div class="markdown-body" v-html="renderedAnswer"></div>
        </article>

        <article class="surface-card">
          <div class="section-title">可信引用</div>
          <div v-if="lastChat?.citations.length" class="stack-list">
            <article v-for="item in lastChat.citations" :key="item.chunk_id" class="info-card">
              <div class="info-title">{{ item.title }}</div>
              <p>{{ item.snippet }}</p>
              <div class="pill-row">
                <span class="pill">score {{ item.score.toFixed(2) }}</span>
                <span class="pill">{{ item.document_id }}</span>
              </div>
            </article>
          </div>
          <div v-else class="empty-state">当前没有引用命中。</div>
        </article>

        <article class="surface-card">
          <div class="section-title">Memory 命中</div>
          <div v-if="lastChat?.memory_hits.length" class="stack-list">
            <article v-for="item in lastChat.memory_hits" :key="item.id" class="info-card">
              <div class="info-title">{{ item.memory_type }}</div>
              <p>{{ item.content }}</p>
              <div class="pill-row">
                <span class="pill">score {{ item.score.toFixed(2) }}</span>
              </div>
            </article>
          </div>
          <div v-else class="empty-state">当前没有命中长期记忆。</div>
        </article>

        <article class="surface-card wide-card">
          <div class="section-title">MCP 工具结果</div>
          <div v-if="lastChat?.tool_results.length" class="stack-list">
            <article v-for="item in lastChat.tool_results" :key="item.tool_name" class="info-card">
              <div class="info-title">{{ item.tool_name }}</div>
              <pre>{{ formatJson(item.result) }}</pre>
            </article>
          </div>
          <div v-else class="empty-state">当前任务没有触发工具调用。</div>
        </article>

        <article class="surface-card wide-card">
          <div class="section-title">A2A / Agent Trace</div>
          <div v-if="lastChat?.trace.length" class="trace-list">
            <article v-for="(item, index) in lastChat.trace" :key="`${item.agent_name}-${index}`" class="trace-card">
              <div class="trace-head">
                <strong>{{ item.agent_name }}</strong>
                <span>{{ item.step_name }}</span>
                <span>{{ item.duration_ms }} ms</span>
              </div>
              <div class="trace-grid">
                <div>
                  <div class="trace-label">输入</div>
                  <pre>{{ formatJson(item.input_data) }}</pre>
                </div>
                <div>
                  <div class="trace-label">输出</div>
                  <pre>{{ formatJson(item.output_data) }}</pre>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="empty-state">执行完成后，这里会显示调用链路。</div>
        </article>
      </section>

      <section v-else-if="activeTab === 'knowledge'" class="content-grid single-column">
        <article class="surface-card">
          <div class="section-title">知识库导入</div>
          <div class="form-grid two-col">
            <label>
              <span>文档标题</span>
              <input v-model="docTitle" placeholder="例如：支付系统事故复盘" />
            </label>
            <label>
              <span>来源类型</span>
              <input v-model="docSource" placeholder="例如：incident-postmortem" />
            </label>
          </div>
          <label>
            <span>原始内容</span>
            <textarea v-model="docContent" rows="10" placeholder="支持直接粘贴 Markdown / TXT 内容；也可以上传 pdf/docx/txt 文件"></textarea>
          </label>
          <label>
            <span>上传文件</span>
            <input ref="fileInputRef" class="native-file-input" type="file" @change="handleFileChange" />
          </label>
          <div class="muted">当前文件：{{ docFileName || '未选择文件' }}</div>
          <div class="action-row">
            <button class="primary-button" @click="uploadDoc">上传到知识库</button>
          </div>
        </article>

        <article class="surface-card">
          <div class="section-title">最近导入的文档</div>
          <div v-if="overview?.latest_documents.length" class="stack-list">
            <article v-for="item in overview.latest_documents" :key="item.id" class="info-card">
              <div class="info-title">{{ item.title }}</div>
              <p>来源：{{ item.source }}</p>
              <div class="pill-row">
                <span class="pill">{{ item.id }}</span>
                <span class="pill">{{ item.created_at }}</span>
              </div>
            </article>
          </div>
          <div v-else class="empty-state">暂无知识文档。</div>
        </article>
      </section>

      <section v-else class="content-grid single-column">
        <article class="surface-card">
          <div class="section-title">新增长期记忆</div>
          <div class="form-grid two-col">
            <label>
              <span>命名空间</span>
              <input v-model="memoryNamespace" placeholder="default" />
            </label>
            <label>
              <span>记忆类型</span>
              <select v-model="memoryType">
                <option value="profile">profile</option>
                <option value="episodic">episodic</option>
                <option value="semantic">semantic</option>
              </select>
            </label>
          </div>
          <label>
            <span>记忆内容</span>
            <textarea v-model="memoryContent" rows="6" placeholder="例如：我负责支付系统，汇报时先结论后依据"></textarea>
          </label>
          <label>
            <span>重要性</span>
            <input v-model.number="memoryImportance" type="number" min="0" max="1" step="0.1" />
          </label>
          <div class="action-row">
            <button class="primary-button" @click="saveMemory">保存记忆</button>
          </div>
        </article>

        <article class="surface-card">
          <div class="section-title">当前用户记忆</div>
          <div v-if="userMemories.length" class="stack-list">
            <article v-for="item in userMemories" :key="item.id" class="info-card">
              <div class="info-title">{{ item.memory_type }}</div>
              <p>{{ item.content }}</p>
              <div class="pill-row">
                <span class="pill">{{ item.namespace }}</span>
                <span class="pill">importance {{ item.importance }}</span>
              </div>
            </article>
          </div>
          <div v-else class="empty-state">这个用户目前还没有长期记忆。</div>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { marked } from 'marked'
import { computed, onMounted, ref } from 'vue'

import InsightCharts from './components/InsightCharts.vue'
import { useDashboardStore } from './stores/dashboard'

const dashboard = useDashboardStore()
const { overview, lastChat, userMemories } = storeToRefs(dashboard)

// 这些状态几乎对应了页面上所有可交互输入项。
const activeTab = ref<'workbench' | 'knowledge' | 'memory'>('workbench')
const userId = ref('alice')
const conversationId = ref('incident-room-1')
const prompt = ref('')
const sending = ref(false)

const docTitle = ref('')
const docSource = ref('incident-postmortem')
const docContent = ref('')
const docFile = ref<File | null>(null)
const docFileName = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

const memoryNamespace = ref('default')
const memoryType = ref<'profile' | 'episodic' | 'semantic'>('profile')
const memoryContent = ref('')
const memoryImportance = ref(0.8)

// 后端回答就是 Markdown 文本，前端这里统一转成 HTML 渲染。
const renderedAnswer = computed(() => marked.parse(lastChat.value?.answer ?? '当前还没有任务结果。'))

function setPrompt(value: string) {
  prompt.value = value
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0] ?? null
  docFile.value = file
  docFileName.value = file?.name ?? ''
}

async function sendPrompt() {
  if (!prompt.value.trim()) {
    return
  }
  sending.value = true
  try {
    await dashboard.sendMessage({
      user_id: userId.value,
      conversation_id: conversationId.value,
      message: prompt.value,
    })
  } finally {
    sending.value = false
  }
}

async function uploadDoc() {
  if (!docTitle.value.trim()) {
    return
  }
  const formData = new FormData()
  formData.append('title', docTitle.value)
  formData.append('source', docSource.value)
  formData.append('content', docContent.value)
  if (docFile.value) {
    formData.append('file', docFile.value)
  }
  await dashboard.uploadDocument(formData)

  // 上传成功后把表单清空，方便下一轮继续导入。
  docTitle.value = ''
  docContent.value = ''
  docFile.value = null
  docFileName.value = ''
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

async function saveMemory() {
  if (!memoryContent.value.trim()) {
    return
  }
  await dashboard.createMemory({
    user_id: userId.value,
    namespace: memoryNamespace.value,
    memory_type: memoryType.value,
    content: memoryContent.value,
    importance: memoryImportance.value,
  })
  memoryContent.value = ''
}

async function loadDemo() {
  activeTab.value = 'workbench'
  sending.value = true
  try {
    await dashboard.loadIncidentDemo(userId.value)
  } finally {
    sending.value = false
  }
}

onMounted(async () => {
  // 页面初始化时先把概览和当前用户记忆拉下来。
  await dashboard.loadOverview()
  await dashboard.loadMemories(userId.value)
})
</script>