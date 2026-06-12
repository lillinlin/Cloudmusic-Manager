<template>
  <div class="bg-slate-800 rounded-2xl border border-slate-700 overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-slate-700">
      <span class="text-sm font-semibold">运行日志</span>
      <button @click="$emit('refresh')" class="text-xs text-slate-400 hover:text-slate-200">刷新</button>
    </div>
    <div ref="box"
         class="h-64 overflow-y-auto p-3 font-mono text-xs space-y-0.5 bg-slate-900">
      <div v-for="(l, i) in logs" :key="i"
           :class="{
             'text-green-400': l.level === 'INFO' && l.msg.includes('✅'),
             'text-red-400':   l.level === 'ERROR' || l.msg.includes('✗'),
             'text-yellow-400': l.level === 'WARNING',
             'text-slate-400': l.level === 'INFO',
           }">
        <span class="text-slate-600">{{ l.ts.slice(11) }}</span>
        {{ l.msg }}
      </div>
      <div v-if="!logs.length" class="text-slate-600">暂无日志</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({ logs: Array })
defineEmits(['refresh'])

const box = ref(null)
watch(() => props.logs?.length, async () => {
  await nextTick()
  if (box.value) box.value.scrollTop = box.value.scrollHeight
})
</script>
