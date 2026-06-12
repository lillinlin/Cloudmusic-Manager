<template>
  <div class="space-y-4 max-w-xl">
    <!-- 基础配置 -->
    <div class="bg-slate-800 rounded-2xl border border-slate-700 p-5">
      <h2 class="font-semibold mb-4 text-sm text-slate-300">基础配置</h2>
      <div class="space-y-3">
        <div>
          <label class="label">API 地址</label>
          <input v-model="form.apiBase" class="input w-full" placeholder="https://your-api.vercel.app" />
        </div>
        <div class="flex gap-3">
          <div class="flex-1">
            <label class="label">每天执行时间</label>
            <input v-model="form.runAt" class="input w-full" placeholder="12:00" />
          </div>
          <div class="flex-1">
            <label class="label">每月配额</label>
            <input v-model.number="form.quotaPerMonth" type="number" min="1" max="31" class="input w-full" />
          </div>
        </div>
        <div>
          <label class="label">分享歌曲 ID</label>
          <input v-model="form.share.id" class="input w-full" placeholder="1297494209" />
        </div>
        <div>
          <label class="label">动态文案 <span class="text-slate-600 font-normal">支持 {{"{{"}}count{{"}}"}} {{"{{"}}date{{"}}"}}</span></label>
          <input v-model="form.share.msg" class="input w-full" />
        </div>
      </div>
    </div>

    <!-- Telegram -->
    <div class="bg-slate-800 rounded-2xl border border-slate-700 p-5">
      <h2 class="font-semibold mb-4 text-sm text-slate-300">Telegram 通知 <span class="text-slate-600 font-normal">（可选）</span></h2>
      <div class="flex gap-3">
        <div class="flex-1">
          <label class="label">Bot Token</label>
          <input v-model="form.telegram.token" class="input w-full" placeholder="1234:ABCD…" />
        </div>
        <div class="flex-1">
          <label class="label">Chat ID</label>
          <input v-model="form.telegram.chat_id" class="input w-full" placeholder="-100…" />
        </div>
      </div>
    </div>

    <!-- 修改密码 -->
    <div class="bg-slate-800 rounded-2xl border border-slate-700 p-5">
      <h2 class="font-semibold mb-4 text-sm text-slate-300">修改密码</h2>
      <div class="space-y-3">
        <input v-model="pw.username" class="input w-full" placeholder="新用户名" />
        <input v-model="pw.password" type="password" class="input w-full" placeholder="新密码" />
        <input v-model="pw.confirm"  type="password" class="input w-full" placeholder="确认新密码" />
        <button @click="changePw" class="btn-ghost w-full py-2 text-sm">修改密码</button>
        <p v-if="pwMsg" class="text-xs" :class="pwOk ? 'text-green-400' : 'text-red-400'">{{ pwMsg }}</p>
      </div>
    </div>

    <!-- 保存 -->
    <button @click="save" :disabled="saving" class="btn-primary w-full py-2.5">
      {{ saving ? '保存中…' : '保存配置' }}
    </button>
    <p v-if="saveMsg" class="text-center text-sm" :class="saveOk ? 'text-green-400' : 'text-red-400'">{{ saveMsg }}</p>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import axios from 'axios'

const emit = defineEmits(['saved'])

const form = reactive({
  apiBase: '', runAt: '12:00', quotaPerMonth: 5,
  share: { type: 'song', id: '', msg: '本月第{{count}}次分享 ✅ {{date}}' },
  telegram: { token: '', chat_id: '' },
  accounts: [],
})
const saving = ref(false)
const saveMsg = ref('')
const saveOk  = ref(true)

const pw    = reactive({ username: '', password: '', confirm: '' })
const pwMsg = ref('')
const pwOk  = ref(true)

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/config')
    form.apiBase        = data.apiBase        || ''
    form.runAt          = data.runAt          || '12:00'
    form.quotaPerMonth  = data.quotaPerMonth  || 5
    form.accounts       = data.accounts       || []
    if (data.share)    Object.assign(form.share,    data.share)
    if (data.telegram) Object.assign(form.telegram, data.telegram)
  } catch {}
})

async function save() {
  saving.value = true
  saveMsg.value = ''
  try {
    await axios.post('/api/config', form)
    saveOk.value  = true
    saveMsg.value = '✅ 保存成功'
    emit('saved')
  } catch {
    saveOk.value  = false
    saveMsg.value = '保存失败'
  } finally {
    saving.value = false
  }
}

async function changePw() {
  pwMsg.value = ''
  if (!pw.username || !pw.password) { pwOk.value = false; pwMsg.value = '请填写用户名和新密码'; return }
  if (pw.password !== pw.confirm)   { pwOk.value = false; pwMsg.value = '两次密码不一致'; return }
  try {
    await axios.post('/api/auth/change_password', { username: pw.username, password: pw.password })
    pwOk.value  = true
    pwMsg.value = '密码已修改，请重新登录'
    setTimeout(() => { localStorage.removeItem('cm_token'); location.reload() }, 1500)
  } catch (e) {
    pwOk.value  = false
    pwMsg.value = e.response?.data?.detail || '修改失败'
  }
}
</script>

<style scoped>
.label { @apply text-slate-400 text-xs block mb-1; }
</style>
