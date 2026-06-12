<template>
  <div class="fixed inset-0 bg-black/70 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-slate-800 rounded-2xl p-6 w-80 text-center border border-slate-700">
      <h3 class="font-semibold mb-1">扫码登录</h3>
      <p class="text-slate-400 text-sm mb-4">{{ name }} — 请用网易云 App 扫描</p>

      <!-- 二维码 -->
      <div class="flex justify-center mb-4">
        <div v-if="qrimg" class="bg-white p-2 rounded-xl inline-block">
          <img :src="qrimg" class="w-44 h-44 object-contain" />
        </div>
        <div v-else class="w-44 h-44 bg-slate-700 rounded-xl flex items-center justify-center text-slate-400 text-sm">
          加载中…
        </div>
      </div>

      <!-- 状态提示 -->
      <div class="text-sm mb-4"
           :class="{
             'text-slate-400': status === 801,
             'text-yellow-400': status === 802,
             'text-green-400': status === 803,
             'text-red-400': status === 800,
           }">
        {{ statusText }}
      </div>

      <button @click="$emit('close')"
              class="text-xs text-slate-500 hover:text-slate-300 transition-colors">
        取消
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name:  String,
  qrimg: String,
  status: Number,
})
defineEmits(['close'])

const statusText = computed(() => ({
  801: '等待扫码…',
  802: '已扫码，请在手机上确认',
  803: '✅ 登录成功！',
  800: '二维码已过期，请关闭重试',
}[props.status] || '等待中…'))
</script>
