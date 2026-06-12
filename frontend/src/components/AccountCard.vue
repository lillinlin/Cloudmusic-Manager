<template>
  <div class="bg-slate-800 rounded-2xl p-5 border transition-colors"
       :class="acc.logged_in ? 'border-slate-700' : 'border-red-500/60'">

    <!-- 头部 -->
    <div class="flex items-center gap-3 mb-4">
      <img v-if="acc.avatar" :src="acc.avatar" class="w-10 h-10 rounded-full object-cover" />
      <div v-else class="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-lg">🎵</div>
      <div class="flex-1 min-w-0">
        <div class="font-semibold text-sm truncate">{{ acc.nickname || acc.name }}</div>
        <div class="text-xs text-slate-500">{{ acc.name }}</div>
      </div>
      <span class="text-xs px-2 py-0.5 rounded-full border"
            :class="acc.logged_in
              ? 'bg-green-500/15 text-green-400 border-green-500/30'
              : 'bg-red-500/15 text-red-400 border-red-500/30 animate-pulse'">
        {{ acc.logged_in ? '已登录' : '未登录' }}
      </span>
    </div>

    <!-- 进度 -->
    <div class="mb-4">
      <div class="flex justify-between text-xs text-slate-400 mb-1.5">
        <span>本月动态</span>
        <span class="font-mono font-semibold">{{ acc.count }} / {{ acc.quota }}</span>
      </div>
      <div class="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div class="h-full bg-red-500 rounded-full transition-all duration-500"
             :style="{ width: pct + '%' }"></div>
      </div>
      <!-- 5个点 -->
      <div class="flex gap-1.5 mt-2">
        <div v-for="i in acc.quota" :key="i"
             class="w-2 h-2 rounded-full transition-colors"
             :class="i <= acc.count ? 'bg-red-400' : 'bg-slate-600'"></div>
      </div>
    </div>

    <!-- 时间 -->
    <div class="text-xs text-slate-500 space-y-0.5 mb-4">
      <div v-if="acc.last_run">上次：{{ acc.last_run }}</div>
      <div v-if="acc.next_run">下次：{{ acc.next_run }}</div>
      <div v-if="!acc.last_run && !acc.next_run" class="text-slate-600">尚未执行</div>
    </div>

    <!-- 按钮 -->
    <div class="flex gap-2">
      <button @click="$emit('login', acc.name)"
              class="flex-1 text-xs py-1.5 rounded-lg transition-colors"
              :class="acc.logged_in
                ? 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                : 'bg-red-500 hover:bg-red-600 text-white'">
        {{ acc.logged_in ? '重新登录' : '扫码登录' }}
      </button>
      <button @click="$emit('run', acc.name)"
              class="flex-1 text-xs py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors">
        手动执行
      </button>
      <button @click="$emit('delete', acc.name)"
              class="px-2.5 py-1.5 rounded-lg bg-slate-700 hover:bg-red-500/20 hover:text-red-400 text-slate-500 text-xs transition-colors">
        🗑
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ acc: Object })
defineEmits(['login', 'run', 'delete'])
const pct = computed(() => props.acc.quota > 0 ? Math.min(100, props.acc.count / props.acc.quota * 100) : 0)
</script>
