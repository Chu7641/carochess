<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

// Popup kết quả ván (thắng / thua / hòa) giữa màn hình; result do useRoomView() tạo ra.
const props = defineProps({ result: { type: Object, default: null } })
const emit = defineEmits(['close', 'new-game'])
const box = ref(null)

watch(() => props.result, async (r) => {
  if (r) {
    await nextTick()
    box.value?.focus()
  }
})

function onKey(e) {
  if (e.key === 'Escape' && props.result) emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <!-- Không đóng khi bấm ra ngoài: người chơi hay bấm tiếp lên bàn cờ, popup tắt trước khi kịp đọc. -->
  <div v-if="result" class="rp-overlay">
    <div ref="box" class="rp-box card" :class="`rp-${result.tone}`" role="dialog" aria-modal="true" tabindex="-1">
      <div class="rp-title">{{ result.title }}</div>
      <p v-if="result.detail" class="rp-detail">{{ result.detail }}</p>
      <p v-if="result.elo" class="rp-elo">{{ result.elo }}</p>
      <div class="rp-buttons">
        <button v-if="result.canRestart" class="btn green" @click="emit('new-game')">Ván mới</button>
        <button class="btn" @click="emit('close')">Đóng</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rp-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.45);
  animation: rp-fade 0.2s ease-out;
}
.rp-box {
  width: min(420px, 100%);
  display: grid;
  gap: 12px;
  text-align: center;
  padding: 28px 24px 22px;
  border-top: 6px solid var(--muted);
  outline: none;
  animation: rp-pop 0.25s ease-out;
}
.rp-win { border-top-color: var(--green); }
.rp-lose { border-top-color: var(--red); }
.rp-draw, .rp-info { border-top-color: var(--blue); }
.rp-title { font-size: 2rem; font-weight: 800; line-height: 1.2; }
.rp-win .rp-title { color: var(--green); }
.rp-lose .rp-title { color: var(--red); }
.rp-draw .rp-title, .rp-info .rp-title { color: var(--blue); }
.rp-detail { margin: 0; color: var(--muted); }
.rp-elo { margin: 0; font-size: 1.15rem; font-weight: 700; }
.rp-buttons { display: flex; justify-content: center; gap: 10px; margin-top: 4px; }
@keyframes rp-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes rp-pop { from { transform: scale(0.85); opacity: 0; } to { transform: scale(1); opacity: 1; } }
</style>
