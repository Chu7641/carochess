<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { createRoom, joinRoom, setName, state, X, O } from '../game.js'

const info = ref({ levels: [] })
const openRooms = ref([])
const joinCode = ref('')
const bot = reactive({ level: 1, side: X, size: 15, strict: false })
const pvp = reactive({ size: 15, strict: false })
let timer = null

async function refreshRooms() {
  try {
    openRooms.value = await (await fetch('/api/rooms')).json()
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
    <div class="card name-card">
      <label class="field">
        <span>Tên của bạn</span>
        <input class="input" maxlength="20" placeholder="Người chơi"
               :value="state.name" @input="setName($event.target.value)" />
      </label>
    </div>

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

      <h3 class="small muted">Phòng đang chờ người chơi</h3>
      <p v-if="!openRooms.length" class="small muted">Chưa có phòng nào. Hãy tạo phòng và gửi mã cho bạn bè.</p>
      <ul class="rooms">
        <li v-for="room in openRooms" :key="room.code">
          <div>
            <strong>{{ room.code }}</strong> · {{ room.host }}
            <div class="small muted">
              {{ room.rows }}×{{ room.cols }} · {{ room.strict ? 'chặn hai đầu' : 'luật tự do' }}
            </div>
          </div>
          <button class="btn green" @click="joinRoom(room.code)">Vào</button>
        </li>
      </ul>
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
.name-card { grid-column: 1 / -1; }
.name-card .field { margin: 0; max-width: 360px; }
.segmented small { opacity: 0.75; }
.join { margin-top: 18px; }
.code { text-transform: uppercase; letter-spacing: 0.2em; font-weight: 700; }
.rooms { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.rooms li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--panel-border);
  border-radius: 10px;
}
h3 { margin: 18px 0 8px; font-weight: 600; }
@media (max-width: 720px) {
  .lobby { grid-template-columns: 1fr; }
}
</style>
