<template>
  <div class="bg-slate-800 rounded-2xl border border-slate-700 p-5">
    <h2 class="font-semibold mb-4">⚙️ 配置</h2>

    <div class="space-y-3 text-sm">
      <div>
        <label class="text-slate-400 block mb-1">API 地址</label>
        <input v-model="form.apiBase" class="input" placeholder="https://..." />
      </div>
      <div class="flex gap-3">
        <div class="flex-1">
          <label class="text-slate-400 block mb-1">每天执行时间</label>
          <input v-model="form.runAt" class="input" placeholder="12:00" />
        </div>
        <div class="flex-1">
          <label class="text-slate-400 block mb-1">每月配额</label>
          <input v-model.number="form.quotaPerMonth" type="number" class="input" />
        </div>
      </div>
      <div>
        <label class="text-slate-400 block mb-1">分享歌曲 ID</label>
        <input v-model="form.share.id" class="input" />
      </div>
      <div>
        <label class="text-slate-400 block mb-1">动态文案 <span class="text-slate-600">（支持 {{count}} {{date}}）</span></label>
        <input v-model="form.share.msg" class="input" />
      </div>

      <div class="border-t border-slate-700 pt-3">
        <p class="text-slate-400 mb-2">Telegram 通知</p>
        <div class="flex gap-3">
          <div class="flex-1">
            <label class="text-slate-500 block mb-1 text-xs">Bot Token</label>
            <input v-model="form.telegram.token" class="input" placeholder="1234:ABCD…" />
          </div>
          <div class="flex-1">
            <label class="text-slate-500 block mb-1 text-xs">Chat ID</label>
            <input v-model="form.telegram.chat_id" class="input" placeholder="-100…" />
          </div>
        </div>
      </div>
    </div>

    <button @click="save"
            :disabled="saving"
            class="mt-4 w-full py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-medium transition-colors disabled:opacity-40">
      {{ saving ? '保存中…' : '保存配置' }}
    </button>
    <p v-if="msg" class="text-center text-xs mt-2" :class="ok ? 'text-green-400' : 'text-red-400'">{{ msg }}</p>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import axios from 'axios'

const form = reactive({
  apiBase: '',
  runAt: '12:00',
  quotaPerMonth: 5,
  share: { type: 'song', id: '', msg: '本月第{{count}}次分享 ✅ {{date}}' },
  telegram: { token: '', chat_id: '' },
  accounts: [],
})
const saving = ref(false)
const msg    = ref('')
const ok     = ref(true)

onMounted(async () => {
  const { data } = await axios.get('/api/config')
  Object.assign(form, {
    ...data,
    share:    { ...form.share,    ...(data.share    || {}) },
    telegram: { ...form.telegram, ...(data.telegram || {}) },
  })
})

async function save() {
  saving.value = true
  msg.value = ''
  try {
    await axios.post('/api/config', form)
    ok.value  = true
    msg.value = '✅ 保存成功'
  } catch {
    ok.value  = false
    msg.value = '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.input {
  @apply w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-1.5
         text-slate-200 text-sm focus:outline-none focus:border-red-500 transition-colors;
}
</style>
