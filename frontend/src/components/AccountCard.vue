<template>
  <div class="bg-slate-800 rounded-2xl p-5 border"
       :class="acc.logged_in ? 'border-slate-700' : 'border-red-500/60'">

    <!-- 头部：头像 + 名称 + 状态 -->
    <div class="flex items-center gap-3 mb-4">
      <img v-if="acc.avatar" :src="acc.avatar"
           class="w-10 h-10 rounded-full object-cover" />
      <div v-else class="w-10 h-10 rounded-full bg-slate-600 flex items-center justify-center text-lg">
        🎵
      </div>
      <div class="flex-1 min-w-0">
        <div class="font-semibold text-sm truncate">
          {{ acc.nickname || acc.name }}
        </div>
        <div class="text-xs text-slate-400">{{ acc.name }}</div>
      </div>
      <!-- 登录状态徽章 -->
      <span v-if="acc.logged_in"
            class="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
        已登录
      </span>
      <span v-else
            class="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse">
        未登录
      </span>
    </div>

    <!-- 进度条 -->
    <div class="mb-3">
      <div class="flex justify-between text-xs text-slate-400 mb-1">
        <span>本月进度</span>
        <span class="font-mono">{{ acc.count }} / {{ acc.quota }}</span>
      </div>
      <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div class="h-full bg-gradient-to-r from-red-500 to-red-400 rounded-full transition-all duration-500"
             :style="{ width: progressPct + '%' }"></div>
      </div>
      <!-- 每天小圆点 -->
      <div class="flex gap-1 mt-2">
        <div v-for="d in 5" :key="d"
             class="w-2 h-2 rounded-full"
             :class="d <= acc.count ? 'bg-red-400' : 'bg-slate-600'">
        </div>
      </div>
    </div>

    <!-- 时间信息 -->
    <div class="text-xs text-slate-500 space-y-0.5 mb-4">
      <div v-if="acc.last_run">上次执行：{{ acc.last_run }}</div>
      <div v-if="acc.next_run">下次执行：{{ acc.next_run }}</div>
    </div>

    <!-- 操作按钮 -->
    <div class="flex gap-2">
      <button v-if="!acc.logged_in"
              @click="$emit('login', acc.name)"
              class="flex-1 text-xs py-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white transition-colors">
        扫码登录
      </button>
      <button @click="$emit('run', acc.name)"
              :disabled="running"
              class="flex-1 text-xs py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors disabled:opacity-40">
        {{ running ? '执行中…' : '手动执行' }}
      </button>
    </div>

  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ acc: Object })
defineEmits(['login', 'run'])

const running = ref(false)
const progressPct = computed(() =>
  props.acc.quota > 0 ? Math.min(100, (props.acc.count / props.acc.quota) * 100) : 0
)
</script>
