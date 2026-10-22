<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { createRoom, joinRoom, state, X, O } from '../game.js'

const info = ref({ levels: [] })
const rooms = ref([])
const STATUS = { waiting: 'Đang chờ', playing: 'Đang chơi', bot: 'Đấu máy' }
// Phòng còn giữ ghế của mình: vào lại. Phòng đang chờ: vào chơi. Còn lại: vào xem.
const mine = (room) => room.players.includes(state.user.username)
const hint = (room) => mine(room) ? 'Vào lại →' : room.status === 'waiting' ? 'Vào ngay →' : 'Xem →'
const joinCode = ref('')
const bot = reactive({ level: 1, side: X, size: 15, strict: false })
const pvp = reactive({ size: 15, strict: false })
let timer = null

async function refreshRooms() {
  try {
    const res = await fetch('/api/rooms')
    if (res.ok) rooms.value = await res.json()
  } catch { /* máy chủ đang khởi động lại */ }
}

onMounted(async () => {
  try {
    info.value = await (await fetch('/api/info')).json()
  } catch { /* dùng giá trị mặc định */ }
  refreshRooms()
  timer = setInterval(refreshRooms, 3000)
})
onUnmounted(() => clearInterval(timer))

// Các kích thước bàn cho chọn; máy chủ vẫn chấp nhận mọi cỡ từ 9 đến 50.
const SIZES = [9, 15, 30, 50]

function startBot() {
  createRoom({ mode: 'bot', level: bot.level, side: bot.side, rows: bot.size, cols: bot.size,
               strict: bot.strict })
}
function startPvp() {
  createRoom({ mode: 'pvp', rows: pvp.size, cols: pvp.size, strict: pvp.strict })
}
</script>

<template>
  <section class="lobby">
    <div class="card">
      <h2>🤖 Chơi với máy</h2>
      <div class="field">
        <span>Độ khó</span>
        <div class="segmented">
          <button v-for="level in info.levels" :key="level.id"
                  :class="{ active: bot.level === level.id }" @click="bot.level = level.id">
            {{ level.name }} <small class="muted-on">· {{ level.seconds }}s</small>
          </button>
        </div>
      </div>
      <div class="field">
        <span>Bạn cầm quân</span>
        <div class="segmented">
          <button :class="{ active: bot.side === X }" @click="bot.side = X">X · đi trước</button>
          <button :class="{ active: bot.side === O }" @click="bot.side = O">O · máy đi trước</button>
        </div>
      </div>
      <label class="field">
        <span>Kích thước bàn</span>
        <select v-model.number="bot.size" class="input">
          <option v-for="n in SIZES" :key="n" :value="n">{{ n }} × {{ n }}</option>
        </select>
      </label>
      <label class="check">
        <input v-model="bot.strict" type="checkbox" />
        <span>Luật chặn hai đầu (bị chặn hai đầu thì không thắng)</span>
      </label>
      <button class="btn green block" :disabled="!state.connected" @click="startBot">
        Bắt đầu ván với máy
      </button>
    </div>

    <div class="card">
      <h2>👥 Chơi với người (mạng LAN)</h2>
      <label class="field">
        <span>Kích thước bàn</span>
        <select v-model.number="pvp.size" class="input">
          <option v-for="n in SIZES" :key="n" :value="n">{{ n }} × {{ n }}</option>
        </select>
      </label>
      <label class="check">
        <input v-model="pvp.strict" type="checkbox" />
        <span>Luật chặn hai đầu</span>
      </label>
      <button class="btn blue block" :disabled="!state.connected" @click="startPvp">
        Tạo phòng mới
      </button>

      <div class="field join">
        <span>Hoặc nhập mã phòng</span>
        <form class="row" @submit.prevent="joinRoom(joinCode)">
          <input v-model="joinCode" class="input code" maxlength="4" placeholder="ABCD" />
          <button class="btn green" :disabled="!state.connected || !joinCode.trim()">Vào phòng</button>
        </form>
      </div>
    </div>

    <div class="card rooms-card">
      <h2>Các phòng <span class="small muted">· tự cập nhật</span></h2>
      <p v-if="!rooms.length" class="small muted">Chưa có phòng nào. Hãy tạo phòng và gửi mã cho bạn bè.</p>
      <div class="rooms">
        <button v-for="room in rooms" :key="room.code" class="room" :class="room.status"
                @click="joinRoom(room.code)">
          <div class="room-head">
            <strong>{{ room.code }}</strong>
            <span class="status">{{ STATUS[room.status] }}</span>
          </div>
          <div class="players">
            {{ room.players.join(' vs ') }}<template v-if="room.status === 'waiting'"> · chờ đối thủ</template>
          </div>
          <div class="small muted">
            {{ room.rows }}×{{ room.cols }} · {{ room.strict ? 'chặn hai đầu' : 'luật tự do' }}
            · {{ room.moves }} nước
          </div>
          <span class="join-hint">{{ hint(room) }}</span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.lobby {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  max-width: 920px;
  margin: 0 auto;
}
.segmented small { opacity: 0.75; }
.join { margin-top: 18px; }
.code { text-transform: uppercase; letter-spacing: 0.2em; font-weight: 700; }
.rooms-card { grid-column: 1 / -1; }
.rooms { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
.room {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--panel-border);
  border-left: 4px solid var(--grey);
  border-radius: 10px;
  background: var(--panel);
  color: var(--text);
  text-align: left;
}
.room { cursor: pointer; transition: transform 0.1s; }
.room:hover { transform: translateY(-2px); border-color: var(--green); }
.room.waiting { border-left-color: var(--green); }
.room.playing { border-left-color: var(--red); }
.room.bot { border-left-color: var(--blue); }
.room-head { display: flex; justify-content: space-between; align-items: center; }
.status { font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 999px; color: #fff; background: var(--grey); }
.waiting .status { background: var(--green); }
.playing .status { background: var(--red); }
.bot .status { background: var(--blue); }
.players { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.join-hint { color: var(--green); font-weight: 700; font-size: 0.85rem; }
.playing .join-hint, .bot .join-hint { color: var(--muted); }
@media (max-width: 720px) {
  .lobby { grid-template-columns: 1fr; }
}
</style>
