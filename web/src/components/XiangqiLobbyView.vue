<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { createRoom, joinRoom, state } from '../game.js'

const info = ref({ xiangqiLevels: [] })
const rooms = ref([])
const STATUS = { waiting: 'Đang chờ', playing: 'Đang chơi', bot: 'Đấu máy' }

const mine = (room) => room.players.includes(state.user?.username)
const hint = (room) => mine(room) ? 'Vào lại →' : room.status === 'waiting' ? 'Vào ngay →' : 'Xem →'
const joinCode = ref('')

const bot = reactive({ level: 1, side: 1 })

let timer = null

async function refreshRooms() {
  try {
    const res = await fetch('/api/rooms')
    if (res.ok) {
      const all = await res.json()
      rooms.value = all.filter((r) => r.game === 'xiangqi')
    }
  } catch { /* máy chủ đang bận */ }
}

onMounted(async () => {
  try {
    const res = await fetch('/api/info')
    if (res.ok) info.value = await res.json()
  } catch { /* dùng mặc định */ }
  refreshRooms()
  timer = setInterval(refreshRooms, 3000)
})
onUnmounted(() => clearInterval(timer))

function startBot() {
  createRoom({
    game: 'xiangqi',
    mode: 'bot',
    level: bot.level,
    side: bot.side,
  })
}
</script>

<template>
  <section class="lobby">
    <!-- Cột chơi với máy -->
    <div class="card">
      <h2>🤖 Chơi cờ tướng với máy</h2>
      <div class="field">
        <span>Độ khó của Bot</span>
        <div class="segmented">
          <button v-for="level in info.xiangqiLevels?.length ? info.xiangqiLevels : [
                    { id: 0, name: 'Dễ' },
                    { id: 1, name: 'Vừa' },
                    { id: 2, name: 'Khó' }
                  ]" :key="level.id"
                  :class="{ active: bot.level === level.id }" @click="bot.level = level.id">
            {{ level.name }}
          </button>
        </div>
      </div>
      <div class="field">
        <span>Bạn cầm quân</span>
        <div class="segmented">
          <button :class="{ active: bot.side === 1 }" @click="bot.side = 1">🔴 Đỏ · đi trước</button>
          <button :class="{ active: bot.side === 2 }" @click="bot.side = 2">⚫ Đen · đi sau</button>
        </div>
      </div>
      <button class="btn green block" :disabled="!state.connected" @click="startBot">
        Bắt đầu ván cờ tướng với máy
      </button>
    </div>

    <!-- Cột danh sách phòng / vào bằng mã -->
    <div class="card">
      <h2>Vào phòng bằng mã</h2>
      <div class="join-row">
        <input v-model="joinCode" class="input uppercase" maxlength="6"
               placeholder="Mã phòng (VD: ABCD)" @keyup.enter="joinRoom(joinCode)">
        <button class="btn green" :disabled="!joinCode || !state.connected"
                @click="joinRoom(joinCode)">Vào</button>
      </div>

      <div class="list-head">
        <h3>Phòng đang hoạt động</h3>
        <span class="muted small">{{ rooms.length }} phòng</span>
      </div>
      <div v-if="!rooms.length" class="empty muted">Chưa có phòng cờ tướng nào. Hãy tạo ván đấu máy ở bên cạnh!</div>
      <div v-else class="room-list">
        <div v-for="room in rooms" :key="room.code" class="room-item" @click="joinRoom(room.code)">
          <div class="code"><strong>{{ room.code }}</strong></div>
          <div class="info">
            <div>{{ room.players.join(' vs ') || 'Chưa có người' }}</div>
            <div class="small muted">{{ STATUS[room.status] ?? room.status }} · {{ room.moves }} nước · {{ room.viewers }} người xem</div>
          </div>
          <button class="btn small">{{ hint(room) }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.lobby {
  display: grid;
  gap: 20px;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}
.card { display: flex; flex-direction: column; gap: 16px; }
h2 { margin: 0; font-size: 1.2rem; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.9rem; }
.segmented {
  display: flex;
  background: var(--bg);
  padding: 3px;
  border-radius: 8px;
  border: 1px solid var(--border);
  gap: 4px;
}
.segmented button {
  flex: 1;
  border: 0;
  background: transparent;
  color: var(--text);
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.15s, color 0.15s;
}
.segmented button.active {
  background: var(--accent);
  color: #fff;
}
.block { width: 100%; padding: 12px; font-size: 1rem; margin-top: 8px; }
.join-row { display: flex; gap: 8px; }
.join-row input { flex: 1; }
.uppercase { text-transform: uppercase; }
.list-head { display: flex; justify-content: space-between; align-items: baseline; margin-top: 8px; }
.list-head h3 { margin: 0; font-size: 1rem; }
.empty { padding: 24px 0; text-align: center; font-size: 0.9rem; }
.room-list { display: flex; flex-direction: column; gap: 8px; max-height: 420px; overflow-y: auto; }
.room-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--bg);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: border-color 0.15s;
}
.room-item:hover { border-color: var(--accent); }
.code { font-size: 1.1rem; color: var(--accent); }
.info { flex: 1; min-width: 0; font-size: 0.9rem; }
</style>

