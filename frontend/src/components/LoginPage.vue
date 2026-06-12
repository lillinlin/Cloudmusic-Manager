<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-900">
    <div class="bg-slate-800 rounded-2xl p-8 w-full max-w-sm border border-slate-700">
      <div class="text-center mb-6">
        <div class="text-4xl mb-2">🎵</div>
        <h1 class="text-xl font-bold">CloudMusic Manager</h1>
        <p class="text-slate-400 text-sm mt-1">请登录以继续</p>
      </div>

      <div class="space-y-3">
        <input v-model="form.username" class="input w-full" placeholder="用户名"
               @keyup.enter="login" />
        <input v-model="form.password" type="password" class="input w-full" placeholder="密码"
               @keyup.enter="login" />
      </div>

      <p v-if="err" class="text-red-400 text-xs mt-2">{{ err }}</p>

      <button @click="login" :disabled="loading"
              class="btn-primary w-full mt-4 py-2">
        {{ loading ? '登录中…' : '登录' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import axios from 'axios'

const emit = defineEmits(['done'])
const form = reactive({ username: '', password: '' })
const err = ref('')
const loading = ref(false)

async function login() {
  err.value = ''
  if (!form.username || !form.password) { err.value = '请填写用户名和密码'; return }
  loading.value = true
  try {
    const { data } = await axios.post('/api/auth/login', {
      username: form.username, password: form.password
    })
    emit('done', data.token)
  } catch (e) {
    err.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
