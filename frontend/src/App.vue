<template>
  <div class="min-h-screen bg-slate-900 text-slate-200">

    <!-- 初始化设置密码页 -->
    <SetupPage v-if="appState === 'setup'" @done="onSetupDone" />

    <!-- 登录页 -->
    <LoginPage v-else-if="appState === 'login'" @done="onLoginDone" />

    <!-- 主面板 -->
    <template v-else-if="appState === 'app'">
      <!-- 顶栏 -->
      <header class="border-b border-slate-800 px-6 py-3 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-xl">🎵</span>
          <span class="font-bold">CloudMusic Manager</span>
        </div>
        <div class="flex items-center gap-3">
          <span class="w-2 h-2 rounded-full" :class="anyOffline ? 'bg-red-400 animate-pulse' : 'bg-green-400'"></span>
          <span class="text-xs text-slate-400">{{ anyOffline ? '有账号需要登录' : '运行正常' }}</span>
          <button @click="logout" class="text-xs text-slate-500 hover:text-slate-300 transition-colors ml-2">退出</button>
        </div>
      </header>

      <div class="max-w-6xl mx-auto p-6">
        <!-- Tab 导航 -->
        <div class="flex gap-1 mb-6 bg-slate-800 rounded-xl p-1 w-fit">
          <button v-for="tab in tabs" :key="tab.id"
                  @click="activeTab = tab.id"
                  class="px-4 py-1.5 rounded-lg text-sm transition-colors"
                  :class="activeTab === tab.id ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'">
            {{ tab.label }}
          </button>
        </div>

        <!-- 账号 Tab -->
        <div v-if="activeTab === 'accounts'">
          <!-- 添加账号 -->
          <div class="flex gap-2 mb-4">
            <input v-model="newAccName" placeholder="输入账号名称（如 acc1）"
                   class="input w-64" @keyup.enter="addAccount" />
            <button @click="addAccount" class="btn-primary px-4">+ 添加账号</button>
          </div>

          <!-- 账号卡片列表 -->
          <div v-if="accounts.length === 0"
               class="text-center py-16 text-slate-500">
            <div class="text-4xl mb-3">👤</div>
            <div>还没有账号，先添加一个吧</div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <AccountCard v-for="acc in accounts" :key="acc.name"
                         :acc="acc"
                         @login="startLogin"
                         @run="manualRun"
                         @delete="deleteAccount" />
          </div>
        </div>

        <!-- 日志 Tab -->
        <div v-if="activeTab === 'logs'">
          <LogViewer :logs="logs" @refresh="fetchLogs" />
        </div>

        <!-- 设置 Tab -->
        <div v-if="activeTab === 'settings'">
          <SettingsPanel @saved="fetchStatus" />
        </div>
      </div>
    </template>

    <!-- 二维码弹窗 -->
    <QrModal v-if="qr.show"
             :name="qr.name" :qrimg="qr.img" :status="qr.status"
             @close="closeQr" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import SetupPage   from './components/SetupPage.vue'
import LoginPage   from './components/LoginPage.vue'
import AccountCard from './components/AccountCard.vue'
import QrModal     from './components/QrModal.vue'
import LogViewer   from './components/LogViewer.vue'
import SettingsPanel from './components/SettingsPanel.vue'

// ── 全局 axios 认证 token ──────────────────
function getToken() { return localStorage.getItem('cm_token') || '' }
axios.interceptors.request.use(cfg => {
  const t = getToken()
  if (t) cfg.headers['Authorization'] = `Bearer ${t}`
  return cfg
})
axios.interceptors.response.use(r => r, err => {
  if (err.response?.status === 401) {
    localStorage.removeItem('cm_token')
    appState.value = 'login'
  }
  return Promise.reject(err)
})

// ── 应用状态 ──────────────────────────────
const appState = ref('loading')  // loading | setup | login | app
const activeTab = ref('accounts')
const tabs = [
  { id: 'accounts', label: '📋 账号' },
  { id: 'logs',     label: '📄 日志' },
  { id: 'settings', label: '⚙️ 设置' },
]

// ── 数据 ──────────────────────────────────
const accounts  = ref([])
const logs      = ref([])
const newAccName = ref('')

const anyOffline = computed(() => accounts.value.some(a => !a.logged_in))

// ── 初始化：判断进哪个页面 ─────────────────
async function init() {
  try {
    const { data } = await axios.get('/api/auth/status')
    if (!data.initialized) {
      appState.value = 'setup'
      return
    }
    if (!getToken()) {
      appState.value = 'login'
      return
    }
    // 验证 token 是否有效
    await axios.get('/api/status')
    appState.value = 'app'
    startPolling()
  } catch {
    appState.value = 'login'
  }
}

function onSetupDone(token) {
  localStorage.setItem('cm_token', token)
  appState.value = 'app'
  startPolling()
}

function onLoginDone(token) {
  localStorage.setItem('cm_token', token)
  appState.value = 'app'
  startPolling()
}

async function logout() {
  try { await axios.post('/api/auth/logout') } catch {}
  localStorage.removeItem('cm_token')
  appState.value = 'login'
  stopPolling()
}

// ── 数据获取 ──────────────────────────────
async function fetchStatus() {
  try {
    const { data } = await axios.get('/api/status')
    accounts.value = data.accounts || []
  } catch {}
}

async function fetchLogs() {
  try {
    const { data } = await axios.get('/api/logs?n=100')
    logs.value = data.logs || []
  } catch {}
}

// ── 账号管理 ──────────────────────────────
async function addAccount() {
  const name = newAccName.value.trim()
  if (!name) return
  try {
    await axios.post(`/api/accounts/add?name=${encodeURIComponent(name)}`)
    newAccName.value = ''
    await fetchStatus()
  } catch (e) {
    alert(e.response?.data?.detail || '添加失败')
  }
}

async function deleteAccount(name) {
  if (!confirm(`确定删除账号 ${name}？Cookie 文件也会一并删除。`)) return
  try {
    await axios.delete(`/api/accounts/${encodeURIComponent(name)}`)
    await fetchStatus()
  } catch {}
}

async function manualRun(name) {
  try {
    await axios.post(`/api/run?name=${encodeURIComponent(name)}`)
    setTimeout(fetchStatus, 3000)
    setTimeout(fetchLogs, 3000)
  } catch {}
}

// ── 二维码登录 ────────────────────────────
const qr = ref({ show: false, name: '', img: '', status: 801 })
let qrTimer = null

async function startLogin(name) {
  qr.value = { show: true, name, img: '', status: 801 }
  try {
    const { data } = await axios.post(`/api/login/start?name=${encodeURIComponent(name)}`)
    if (data.ok) {
      qr.value.img = data.qrimg
      qrTimer = setInterval(async () => {
        try {
          const { data: s } = await axios.get(`/api/login/status?name=${encodeURIComponent(name)}`)
          qr.value.status = s.status
          if (s.status === 803) {
            clearInterval(qrTimer)
            setTimeout(() => { qr.value.show = false; fetchStatus() }, 1500)
          }
          if (s.status === 800) clearInterval(qrTimer)
        } catch {}
      }, 2000)
    } else {
      alert(data.msg || '获取二维码失败')
      qr.value.show = false
    }
  } catch {}
}

function closeQr() {
  clearInterval(qrTimer)
  qr.value.show = false
}

// ── 轮询 ──────────────────────────────────
let statusTimer = null
let logTimer    = null

function startPolling() {
  fetchStatus()
  fetchLogs()
  statusTimer = setInterval(fetchStatus, 10000)
  logTimer    = setInterval(fetchLogs,   8000)
}

function stopPolling() {
  clearInterval(statusTimer)
  clearInterval(logTimer)
}

onMounted(init)
onUnmounted(stopPolling)
</script>

<style>
.input {
  @apply bg-slate-800 border border-slate-600 rounded-lg px-3 py-2
         text-sm text-slate-200 focus:outline-none focus:border-red-500 transition-colors;
}
.btn-primary {
  @apply bg-red-500 hover:bg-red-600 text-white text-sm rounded-lg py-2
         transition-colors disabled:opacity-40;
}
.btn-ghost {
  @apply bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg py-2
         transition-colors;
}
</style>
