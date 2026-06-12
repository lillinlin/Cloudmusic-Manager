<template>
  <div class="min-h-screen p-4 md:p-8 max-w-5xl mx-auto">

    <!-- 标题栏 -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-bold">🎵 网易云自动分享</h1>
        <p class="text-slate-500 text-xs mt-0.5">CloudMusic Auto Share Dashboard</p>
      </div>
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full" :class="anyOffline ? 'bg-red-400 animate-pulse' : 'bg-green-400'"></span>
        <span class="text-xs text-slate-400">{{ anyOffline ? '有账号需要登录' : '运行正常' }}</span>
      </div>
    </div>

    <!-- 账号卡片 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
      <AccountCard
        v-for="acc in accounts" :key="acc.name"
        :acc="acc"
        @login="startLogin"
        @run="manualRun"
      />
    </div>

    <!-- 日志 + 设置 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <LogViewer :logs="logs" @refresh="fetchLogs" />
      <SettingsPanel />
    </div>

    <!-- 二维码弹窗 -->
    <QrModal
      v-if="qr.show"
      :name="qr.name"
      :qrimg="qr.img"
      :status="qr.status"
      @close="qr.show = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import AccountCard  from './components/AccountCard.vue'
import QrModal      from './components/QrModal.vue'
import LogViewer    from './components/LogViewer.vue'
import SettingsPanel from './components/SettingsPanel.vue'

const accounts = ref([])
const logs     = ref([])
const qr       = ref({ show: false, name: '', img: '', status: 801 })

const anyOffline = computed(() => accounts.value.some(a => !a.logged_in))

// ── 轮询 ─────────────────────────────────
let statusTimer = null
let logTimer    = null
let qrTimer     = null

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

// ── 登录 ─────────────────────────────────
async function startLogin(name) {
  qr.value = { show: true, name, img: '', status: 801 }
  try {
    const { data } = await axios.post(`/api/login/start?name=${name}`)
    if (data.ok) {
      qr.value.img = data.qrimg
      // 轮询扫码状态
      qrTimer = setInterval(async () => {
        const { data: s } = await axios.get(`/api/login/status?name=${name}`)
        qr.value.status = s.status
        if (s.status === 803) {
          clearInterval(qrTimer)
          setTimeout(() => { qr.value.show = false; fetchStatus() }, 1500)
        }
        if (s.status === 800) clearInterval(qrTimer)
      }, 2000)
    }
  } catch {}
}

// ── 手动执行 ──────────────────────────────
async function manualRun(name) {
  try {
    await axios.post(`/api/run?name=${name}`)
    setTimeout(fetchStatus, 3000)
    setTimeout(fetchLogs,   3000)
  } catch {}
}

// ── 生命周期 ──────────────────────────────
onMounted(() => {
  fetchStatus()
  fetchLogs()
  statusTimer = setInterval(fetchStatus, 10000)
  logTimer    = setInterval(fetchLogs,   8000)
})

onUnmounted(() => {
  clearInterval(statusTimer)
  clearInterval(logTimer)
  clearInterval(qrTimer)
})
</script>
