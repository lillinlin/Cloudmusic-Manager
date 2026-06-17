<template>
  <div class="bg-slate-800 rounded-2xl p-5 border transition-colors"
       :class="acc.logged_in ? 'border-slate-700' : 'border-red-500/60'">

    <!-- 头部 -->
    <div class="flex items-center gap-3 mb-4">
      <img v-if="acc.avatar" :src="acc.avatar" class="w-10 h-10 rounded-full object-cover" />
      <div v-else class="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-lg">
        {{ acc.role === 'listener' ? '🎧' : '🎵' }}
      </div>
      <div class="flex-1 min-w-0">
        <div class="font-semibold text-sm truncate">{{ acc.nickname || acc.name }}</div>
        <div class="flex items-center gap-1.5 mt-0.5">
          <span class="text-xs text-slate-500">{{ acc.name }}</span>
          <span class="text-xs px-1.5 py-0 rounded border"
                :class="acc.role === 'listener'
                  ? 'bg-blue-500/15 text-blue-400 border-blue-500/30'
                  : 'bg-purple-500/15 text-purple-400 border-purple-500/30'">
            {{ acc.role === 'listener' ? '听歌保活' : '动态分享' }}
          </span>
        </div>
      </div>
      <span class="text-xs px-2 py-0.5 rounded-full border flex-shrink-0"
            :class="acc.logged_in
              ? 'bg-green-500/15 text-green-400 border-green-500/30'
              : 'bg-red-500/15 text-red-400 border-red-500/30 animate-pulse'">
        {{ acc.logged_in ? '已登录' : '未登录' }}
      </span>
    </div>

    <!-- sharer：进度 -->
    <div v-if="acc.role === 'sharer'" class="mb-4">
      <div class="flex justify-between text-xs text-slate-400 mb-1.5">
        <span>本月动态</span>
        <span class="font-mono font-semibold">{{ acc.count }} / {{ acc.quota }}</span>
      </div>
      <div class="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div class="h-full bg-red-500 rounded-full transition-all duration-500"
             :style="{ width: pct + '%' }"></div>
      </div>
      <div class="flex gap-1.5 mt-2">
        <div v-for="i in acc.quota" :key="i"
             class="w-2 h-2 rounded-full transition-colors"
             :class="i <= acc.count ? 'bg-red-400' : 'bg-slate-600'"></div>
      </div>
    </div>

    <!-- listener：今日听歌 -->
    <div v-else class="mb-4">
      <div class="flex justify-between text-xs text-slate-400 mb-1.5">
        <span>今日听歌</span>
        <span class="font-mono font-semibold">{{ acc.listen_today }} / {{ acc.listen_daily }}</span>
      </div>
      <div class="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div class="h-full bg-blue-500 rounded-full transition-all duration-500"
             :style="{ width: listenPct + '%' }"></div>
      </div>
    </div>

    <!-- 歌曲ID -->
    <div class="mb-3">
      <div class="text-xs text-slate-500 mb-1">
        {{ acc.role === 'listener' ? '听歌 ID' : '分享歌曲 ID' }}
        <span class="text-slate-600 ml-1">（空则用全局设置）</span>
      </div>
      <div class="flex gap-1.5">
        <input v-model="localSongId" class="input flex-1 text-xs py-1"
               :placeholder="acc.role === 'listener' ? '歌曲ID' : '歌曲ID'" />
        <button @click="saveSettings"
                class="text-xs px-2.5 py-1 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors">
          保存
        </button>
      </div>
    </div>

    <!-- listener：每日次数 -->
    <div v-if="acc.role === 'listener'" class="mb-3">
      <div class="text-xs text-slate-500 mb-1">每日听歌次数</div>
      <input v-model.number="localListenDaily" type="number" min="1" max="100"
             class="input w-full text-xs py-1" />
    </div>

    <!-- 时间 -->
    <div class="text-xs text-slate-600 space-y-0.5 mb-4">
      <div v-if="acc.last_run">上次：{{ acc.last_run }}</div>
      <div v-if="acc.next_run">下次：{{ acc.next_run }}</div>
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
import { computed, ref, watch } from 'vue'
import axios from 'axios'

const props = defineProps({ acc: Object })
const emit  = defineEmits(['login', 'run', 'delete', 'updated'])

const localSongId     = ref(props.acc.song_id     || '')
const localListenDaily = ref(props.acc.listen_daily || 10)

watch(() => props.acc, (v) => {
  localSongId.value      = v.song_id     || ''
  localListenDaily.value = v.listen_daily || 10
})

const pct       = computed(() => props.acc.quota > 0 ? Math.min(100, props.acc.count / props.acc.quota * 100) : 0)
const listenPct = computed(() => props.acc.listen_daily > 0 ? Math.min(100, props.acc.listen_today / props.acc.listen_daily * 100) : 0)

async function saveSettings() {
  try {
    await axios.patch(`/api/accounts/${encodeURIComponent(props.acc.name)}`, {
      name:         props.acc.name,
      role:         props.acc.role,
      song_id:      localSongId.value,
      listen_daily: localListenDaily.value,
    })
    emit('updated')
  } catch {}
}
</script>
