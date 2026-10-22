<script setup>
import { onMounted, watch } from 'vue'
import { checkSession, chooseGame, joinRoom, logout, state } from './game.js'
import LoginView from './components/LoginView.vue'
import GamesView from './components/GamesView.vue'
import LobbyView from './components/LobbyView.vue'
import GameView from './components/GameView.vue'
import AdminView from './components/AdminView.vue'
import PasswordView from './components/PasswordView.vue'

const TITLES = { caro: 'CỜ CARO · GOMOKU', admin: 'QUẢN TRỊ', password: 'TÀI KHOẢN' }

// Link mời dạng /?room=ABCD: vào thẳng phòng đó ngay khi đăng nhập xong.
const invite = new URLSearchParams(location.search).get('room')
watch(() => state.user, (user) => {
  if (user && invite && !state.code) {
    chooseGame('caro')
    joinRoom(invite)
  }
})

onMounted(checkSession)
</script>

<template>
  <header class="topbar">
    <h1>
      <button v-if="state.user && state.game && !state.code" class="back"
              title="Chọn trò chơi khác" @click="chooseGame(null)">←</button>
      {{ TITLES[state.game] ?? 'TRÒ CHƠI LAN' }}
    </h1>
    <div v-if="state.user" class="who">
      <button v-if="state.user.isAdmin && state.game !== 'admin' && !state.code" class="btn small"
              @click="chooseGame('admin')">Quản trị</button>
      <span class="conn" :class="{ off: !state.connected }"
            :title="state.connected ? 'Đã kết nối' : 'Đang kết nối lại…'"></span>
      <button class="name" :disabled="!!state.code" title="Đổi mật khẩu"
              @click="chooseGame('password')">{{ state.user.username }}</button>
      <span class="elo" title="Điểm elo">{{ state.user.elo }} elo</span>
      <span v-if="state.user.isAdmin" class="badge">Admin</span>
      <button class="btn small" @click="logout">Đăng xuất</button>
    </div>
  </header>
  <main>
    <div v-if="!state.checked" class="loading muted">Đang tải…</div>
    <LoginView v-else-if="!state.user" />
    <template v-else-if="state.game === 'caro'">
      <GameView v-if="state.code && state.room" />
      <div v-else-if="state.code" class="loading muted">Đang vào phòng {{ state.code }}…</div>
      <LobbyView v-else />
    </template>
    <AdminView v-else-if="state.game === 'admin' && state.user.isAdmin" />
    <PasswordView v-else-if="state.game === 'password'" />
    <GamesView v-else />
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
  padding: 10px 20px;
  background: var(--title);
  color: #fff5de;
}
h1 { margin: 0; font-size: 1.2rem; letter-spacing: 0.04em; display: flex; align-items: center; gap: 10px; }
.back {
  border: 0; background: rgb(255 255 255 / 0.12); color: inherit;
  border-radius: 8px; width: 32px; height: 32px; cursor: pointer; font-size: 1.1rem;
}
.who { display: flex; align-items: center; gap: 10px; font-size: 0.9rem; min-width: 0; }
.who .btn { padding: 6px 10px; }
.conn { width: 9px; height: 9px; border-radius: 50%; background: #2fae62; flex: none; }
.conn.off { background: #e0786c; }
.name {
  border: 0; background: none; color: inherit; font: inherit; cursor: pointer;
  padding: 0; text-decoration: underline dotted; text-underline-offset: 3px;
}
.name:disabled { cursor: default; text-decoration: none; }
.elo { color: #e8d9b8; font-size: 0.8rem; white-space: nowrap; }
.badge { background: var(--accent); color: #2b2a27; border-radius: 6px; padding: 1px 6px; font-size: 0.75rem; font-weight: 700; }
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
@media (max-width: 560px) {
  h1 { font-size: 1rem; }
  .who > .name { max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
}
</style>
