<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  leaveRoom,
  move,
  passTurn,
  respond,
  restart,
  showError,
  state,
  toggleReady,
  undo,
} from '../game.js'
import GoBoard from './GoBoard.vue'

const room = computed(() => state.room)
const you = computed(() => room.value.you)
const isBot = computed(() => room.value.mode === 'bot')
const playing = computed(() => room.value.winner === 0 && !room.value.waiting && room.value.started)
const needReady = computed(() =>
  room.value.winner === 0 && !room.value.waiting && !room.value.started)
const iAmReady = computed(() => room.value.ready?.includes(you.value))
const canPlay = computed(() => playing.value && you.value === room.value.current)

const lanIps = ref([])
const copied = ref(false)
const now = ref(Date.now())
let ticker = null

onMounted(async () => {
  ticker = setInterval(() => { now.value = Date.now() }, 200)
  try {
    lanIps.value = (await (await fetch('/api/info')).json()).lan
  } catch { /* dùng mặc định */ }
})
onUnmounted(() => clearInterval(ticker))

watch(() => room.value?.notice, (notice) => { if (notice) showError(notice) })

const request = computed(() => {
  const r = room.value.request
  if (!r) return null
  const mine = r.side === you.value
  return {
    mine,
    canAnswer: !mine && you.value != null,
    text: mine ? 'Đang chờ đối thủ đồng ý cho bạn đi lại…'
               : `${player(r.side)?.name ?? (r.side === 1 ? 'Đen' : 'Trắng')} xin đi lại.`,
  }
})

const turnLeft = computed(() => {
  const r = room.value
  if (!r || r.turnLeft == null) return null
  return Math.max(0, Math.ceil(r.turnLeft - (now.value - (r.receivedAt || now.value)) / 1000))
})

function newGame() {
  const r = room.value
  if (!isBot.value && playing.value && r.moves
      && !confirm('Ván cờ chưa kết thúc. Đầu hàng / mở ván mới sẽ bị tính là bạn thua (trừ Elo). Bạn chắc chắn?')) return
  restart()
}

const inviteLink = computed(() => {
  const local = ['localhost', '127.0.0.1', '::1', '[::1]'].includes(location.hostname)
  const host = local && lanIps.value.length
    ? `${lanIps.value[0]}${location.port ? `:${location.port}` : ''}`
    : location.host
  return `${location.protocol}//${host}/?room=${room.value.code}`
})

async function copyLink() {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
  } catch {
    const input = document.createElement('textarea')
    input.value = inviteLink.value
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    input.remove()
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

const player = (side) => room.value.players?.[String(side)]

const status = computed(() => {
  const r = room.value
  if (!r) return { text: '', tone: 'muted' }
  if (r.winner) {
    const who = player(r.winner)
    const mine = r.winner === you.value
    const name = r.winner === 1 ? 'Đen' : 'Trắng'
    return {
      text: you.value ? (mine ? 'Bạn thắng! 🎉' : `${who?.name ?? name} thắng!`)
                      : `${who?.name ?? name} thắng!`,
      tone: mine ? 'green' : 'red',
    }
  }
  if (r.waiting) return { text: 'Đang chờ đối thủ vào phòng…', tone: 'muted' }
  if (!r.started) return { text: 'Chờ cả hai bên bấm Sẵn sàng…', tone: 'muted' }
  if (r.botThinking) return { text: 'Bot cờ vây đang tính toán…', tone: 'blue' }
  if (canPlay.value) return { text: 'Đến lượt bạn đi', tone: 'green' }
  const currentName = r.current === 1 ? 'Đen' : 'Trắng'
  return { text: `Lượt của ${player(r.current)?.name ?? currentName}`, tone: 'muted' }
})

function onPlay(r, c) {
  move(r, c)
}

function onPass() {
  if (confirm('Bạn có chắc chắn muốn bỏ lượt này không? (Nếu đối thủ cũng bỏ lượt, ván cờ sẽ kết thúc để tính điểm)')) {
    passTurn()
  }
}
</script>

<template>
  <div v-if="room" class="game-view">
    <!-- Thanh thông tin phòng và người chơi -->
    <header class="room-bar">
      <div class="room-info">
        <span class="room-code">Phòng <strong>{{ room.code }}</strong></span>
        <span class="meta">Bàn cờ vây {{ room.size || room.rows }}×{{ room.size || room.cols }} · Komi: {{ room.komi }}</span>
        <button v-if="!isBot" class="btn small" :class="{ green: copied }" @click="copyLink">
          {{ copied ? '✓ Đã chép link mời' : '📋 Chép link mời bạn' }}
        </button>
      </div>
      <button class="btn small" @click="leaveRoom">Rời phòng</button>
    </header>

    <!-- Thẻ hai người chơi -->
    <div class="players-bar">
      <!-- Đen -->
      <div class="player-card" :class="{
        active: room.current === 1 && playing,
        winner: room.winner === 1,
        isYou: you === 1
      }">
        <div class="stone-icon black">⚫</div>
        <div class="player-meta">
          <div class="name-row">
            <strong>{{ player(1)?.name || 'Đang chờ…' }}</strong>
            <span v-if="you === 1" class="tag you">Bạn</span>
            <span v-if="needReady && room.ready?.includes(1)" class="tag ready">Đã sẵn sàng</span>
          </div>
          <div class="sub-row small muted">
            <span v-if="player(1)?.elo">{{ player(1).elo }} elo</span>
            <span class="prisoners">Tù binh bắt được: <strong>{{ room.captured?.['1'] ?? 0 }}</strong></span>
          </div>
        </div>
      </div>

      <!-- Trung tâm: Trạng thái & Đồng hồ -->
      <div class="center-status">
        <div class="status-msg" :class="status.tone">{{ status.text }}</div>
        <div v-if="turnLeft != null && playing" class="turn-timer" :class="{ urgent: turnLeft <= 5 }">
          ⏱ {{ turnLeft }}s
        </div>
      </div>

      <!-- Trắng -->
      <div class="player-card right" :class="{
        active: room.current === 2 && playing,
        winner: room.winner === 2,
        isYou: you === 2
      }">
        <div class="player-meta">
          <div class="name-row">
            <span v-if="needReady && room.ready?.includes(2)" class="tag ready">Đã sẵn sàng</span>
            <span v-if="you === 2" class="tag you">Bạn</span>
            <strong>{{ player(2)?.name || 'Đang chờ…' }}</strong>
          </div>
          <div class="sub-row small muted">
            <span class="prisoners">Tù binh bắt được: <strong>{{ room.captured?.['2'] ?? 0 }}</strong></span>
            <span v-if="player(2)?.elo">{{ player(2).elo }} elo</span>
          </div>
        </div>
        <div class="stone-icon white">⚪</div>
      </div>
    </div>

    <!-- Bảng thông báo yêu cầu đi lại (nếu có) -->
    <div v-if="request" class="request-banner">
      <span>{{ request.text }}</span>
      <div v-if="request.canAnswer" class="req-actions">
        <button class="btn green small" @click="respond(true)">Đồng ý</button>
        <button class="btn red small" @click="respond(false)">Từ chối</button>
      </div>
    </div>

    <!-- Bảng tổng kết điểm số khi ván cờ kết thúc -->
    <div v-if="room.score" class="score-modal card">
      <h3>Kết quả đếm điểm diện tích (Tromp-Taylor)</h3>
      <div class="score-cols">
        <div class="score-side black-score" :class="{ win: room.winner === 1 }">
          <h4>⚫ Đen: {{ room.score.black.total }} điểm</h4>
          <p class="small muted">Quân sống: {{ room.score.black.stones }} · Đất: {{ room.score.black.territory }}</p>
        </div>
        <div class="score-side white-score" :class="{ win: room.winner === 2 }">
          <h4>⚪ Trắng: {{ room.score.white.total }} điểm</h4>
          <p class="small muted">
            Quân sống: {{ room.score.white.stones }} · Đất: {{ room.score.white.territory }} · Komi: {{ room.score.white.komi }}
          </p>
        </div>
      </div>
      <div class="score-summary">
        <strong>{{ room.winner === 1 ? 'Đen' : 'Trắng' }} thắng cách biệt {{ room.score.margin }} mục!</strong>
      </div>
    </div>

    <!-- Bàn cờ SVG -->
    <GoBoard
      :room="room"
      :can-play="canPlay"
      :ghost-side="you || 1"
      @play="onPlay"
    />

    <!-- Thanh nút hành động bên dưới bàn cờ -->
    <footer class="controls-bar">
      <!-- Nút Sẵn sàng cho đấu người -->
      <button v-if="needReady && you" class="btn green" @click="toggleReady">
        {{ iAmReady ? 'Hủy sẵn sàng' : '✓ Sẵn sàng vào ván' }}
      </button>

      <!-- Nút Bỏ lượt (Pass) -->
      <button v-if="canPlay" class="btn blue" @click="onPass">
        ⏭ Bỏ lượt (Pass)
      </button>

      <!-- Nút Xin đi lại (Undo) -->
      <button v-if="you && playing && room.moves > 0" class="btn" @click="undo">
        ↶ Xin đi lại
      </button>

      <!-- Nút Ván mới / Đầu hàng -->
      <button v-if="you && (room.winner !== 0 || !playing || room.moves > 0)" class="btn" @click="newGame">
        {{ playing && !isBot ? '🏳 Đầu hàng / Ván mới' : '🔄 Ván mới' }}
      </button>
    </footer>
  </div>
</template>

<style scoped>
.game-view {
  display: grid;
  gap: 12px;
  max-width: 1040px;
  margin: 0 auto;
}
.room-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--panel);
  padding: 8px 16px;
  border-radius: 10px;
  border: 1px solid var(--panel-border);
}
.room-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.room-code strong {
  color: var(--accent);
  letter-spacing: 0.1em;
  font-size: 1.1rem;
}
.players-bar {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
}
.player-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--panel);
  border: 2px solid var(--panel-border);
  border-radius: 10px;
  transition: all 0.2s;
}
.player-card.right {
  justify-content: flex-end;
  text-align: right;
}
.player-card.active {
  border-color: #e5a93c;
  box-shadow: 0 0 10px rgb(229 169 60 / 0.3);
}
.player-card.winner {
  border-color: var(--green);
  background: rgb(47 174 98 / 0.1);
}
.stone-icon { font-size: 1.8rem; line-height: 1; }
.name-row { display: flex; align-items: center; gap: 6px; }
.right .name-row { justify-content: flex-end; }
.tag {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
}
.tag.you { background: var(--blue); color: #fff; }
.tag.ready { background: var(--green); color: #fff; }
.sub-row { display: flex; gap: 8px; }
.right .sub-row { justify-content: flex-end; }
.prisoners strong { color: var(--accent); }
.center-status {
  text-align: center;
  padding: 0 10px;
  min-width: 170px;
}
.status-msg {
  font-weight: 700;
  font-size: 0.95rem;
}
.status-msg.green { color: var(--green); }
.status-msg.red { color: var(--red); }
.status-msg.blue { color: var(--blue); }
.turn-timer {
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 4px;
  color: var(--text);
}
.turn-timer.urgent {
  color: var(--red);
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.request-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #3b2e16;
  border: 1px solid #7a5a22;
  color: #f7dfa5;
  padding: 8px 16px;
  border-radius: 8px;
}
.req-actions { display: flex; gap: 8px; }
.score-modal {
  padding: 16px;
  text-align: center;
  border: 2px solid var(--accent);
}
.score-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin: 12px 0;
}
.score-side {
  padding: 10px;
  background: rgb(0 0 0 / 0.15);
  border-radius: 8px;
}
.score-side.win {
  border: 2px solid var(--green);
  background: rgb(47 174 98 / 0.15);
}
.score-summary {
  font-size: 1.1rem;
  color: var(--accent);
}
.controls-bar {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 0;
}
@media (max-width: 720px) {
  .players-bar {
    grid-template-columns: 1fr 1fr;
  }
  .center-status {
    grid-column: 1 / -1;
    order: -1;
  }
}
</style>
