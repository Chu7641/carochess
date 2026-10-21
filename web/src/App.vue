<script setup>
import { onMounted } from 'vue'
import { connect, joinRoom, state } from './game.js'
import LobbyView from './components/LobbyView.vue'
import GameView from './components/GameView.vue'

onMounted(() => {
  // Mở link mời dạng /?room=ABCD: vào thẳng phòng đó.
  const code = new URLSearchParams(location.search).get('room')
  if (code) joinRoom(code)
  connect()
})
</script>

<template>
  <header class="topbar">
    <h1>CỜ CARO · GOMOKU</h1>
    <span class="conn" :class="{ off: !state.connected }">
      {{ state.connected ? 'Đã kết nối' : 'Đang kết nối lại…' }}
    </span>
  </header>
  <main>
    <GameView v-if="state.code && state.room" />
    <div v-else-if="state.code" class="loading muted">Đang vào phòng {{ state.code }}…</div>
    <LobbyView v-else />
  </main>
  <Transition name="toast">
    <div v-if="state.error" class="toast" role="alert">{{ state.error }}</div>
  </Transition>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  background: var(--title);
  color: #fff5de;
}
h1 { margin: 0; font-size: 1.3rem; letter-spacing: 0.04em; }
.conn { font-size: 0.8rem; color: #9fd8b4; }
.conn.off { color: #f2a59c; }
main { padding: 16px; max-width: 1280px; margin: 0 auto; }
.loading { text-align: center; padding: 60px 0; }
.toast {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  background: var(--red);
  color: #fff;
  padding: 10px 18px;
  border-radius: 10px;
  box-shadow: 0 6px 20px rgb(0 0 0 / 0.25);
  max-width: calc(100vw - 32px);
}
.toast-enter-active, .toast-leave-active { transition: opacity 0.2s, transform 0.2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translate(-50%, 10px); }
</style>
