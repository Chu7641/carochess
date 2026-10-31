<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { createRoom, joinRoom, state } from '../game.js'

const info = ref({ battleshipLevels: [] })
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
      rooms.value = all.filter((r) => r.game === 'battleship')
    }
  } catch {
    /* máy chủ đang bận */
  }
}

onMounted(async () => {
  try {
    const res = await fetch('/api/info')
    if (res.ok) info.value = await res.json()
  } catch {
    /* dùng mặc định */
  }
  refreshRooms()
  timer = setInterval(refreshRooms, 3000)
})
onUnmounted(() => clearInterval(timer))

function startBot() {
  createRoom({
    game: 'battleship',
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
      <h2>🤖 Đấu với máy</h2>
      <div class="field">
        <span>Độ khó</span>
        <div class="segmented">
          <button
            v-for="level in info.battleshipLevels?.length ? info.battleshipLevels : [
              { id: 0, name: 'Dễ' },
              { id: 1, name: 'Vừa' },
              { id: 2, name: 'Khó' }
            ]"
            :key="level.id"
            :class="{ active: bot.level === level.id }"
            @click="bot.level = level.id"
          >
            {{ level.name }}
          </button>
        </div>
      </div>
      <div class="field">
        <span>Lượt bắn trước</span>
        <div class="segmented">
          <button :class="{ active: bot.side === 1 }" @click="bot.side = 1">
            🎯 Bạn bắn trước
          </button>
          <button :class="{ active: bot.side === 2 }" @click="bot.side = 2">
            🤖 Máy bắn trước
          </button>
        </div>
      </div>
      <button class="btn green block" :disabled="!state.connected" @click="startBot">
        Bắt đầu trận chiến
      </button>

      <p class="small muted note-pvp">
        * Đợt 1 chỉ hỗ trợ đấu với máy. Chế độ đấu người qua mạng LAN sẽ có ở đợt cập nhật tiếp theo.
      </p>
    </div>

    <!-- Cột danh sách phòng -->
    <div class="card">
      <h2>🚢 Các phòng hải chiến</h2>
      <div class="field join">
        <input
          v-model="joinCode"
          placeholder="Mã phòng (ví dụ ABCD)"
          maxlength="6"
          @keyup.enter="joinCode && joinRoom(joinCode)"
        />
        <button class="btn" :disabled="!joinCode || !state.connected" @click="joinRoom(joinCode)">
          Vào phòng
        </button>
      </div>

      <div v-if="rooms.length" class="rooms">
        <div
          v-for="room in rooms"
          :key="room.code"
          class="room"
          :class="{ mine: mine(room) }"
          @click="joinRoom(room.code)"
        >
          <div class="top">
            <strong>Phòng {{ room.code }}</strong>
            <span class="tag" :class="room.status">{{ STATUS[room.status] }}</span>
          </div>
          <div class="desc small muted">
            <span>{{ room.players.join(' vs ') || 'Chưa có ai' }}</span>
            <span v-if="room.moves">· {{ room.moves }} phát bắn</span>
          </div>
          <span class="go small">{{ hint(room) }}</span>
        </div>
      </div>
      <p v-else class="small muted empty">Chưa có phòng hải chiến nào đang mở.</p>
    </div>
  </section>
</template>

<style scoped>
.lobby {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  max-width: 920px;
  margin: 0 auto;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
h2 {
  margin: 0;
  font-size: 1.15rem;
}
.field {
  display: grid;
  gap: 6px;
}
.join {
  display: flex;
  gap: 8px;
}
.join input {
  flex: 1;
  text-transform: uppercase;
}
.note-pvp {
  margin: 4px 0 0;
  line-height: 1.4;
}
.rooms {
  display: grid;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
}
.room {
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  display: grid;
  gap: 4px;
  transition: border-color 0.15s;
}
.room:hover {
  border-color: var(--accent);
}
.room.mine {
  border-color: var(--accent);
  background: rgba(238, 182, 61, 0.08);
}
.room .top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tag {
  font-size: 0.75rem;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.tag.waiting {
  background: var(--accent);
  color: #2b2a27;
}
.tag.playing {
  background: var(--blue);
  color: #fff;
}
.tag.bot {
  background: var(--grey);
  color: #fff;
}
.desc {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.go {
  color: var(--blue);
  font-weight: 600;
}
.empty {
  margin: 8px 0;
}
</style>

