<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  leaveRoom,
  movePiece,
  restart,
  showError,
  state,
  undo,
} from '../game.js'
import XiangqiBoard from './XiangqiBoard.vue'

const room = computed(() => state.room)
const you = computed(() => room.value?.you)
const isBot = computed(() => room.value?.mode === 'bot')
const playing = computed(() => room.value?.winner === 0 && room.value?.started)
const canPlay = computed(() => playing.value && you.value === room.value?.current && !room.value?.botThinking)

const now = ref(Date.now())
let ticker = null

onMounted(() => {
  ticker = setInterval(() => { now.value = Date.now() }, 200)
})
onUnmounted(() => clearInterval(ticker))

watch(() => room.value?.notice, (notice) => {
  if (notice && notice !== 'Chiếu tướng!') {
    showError(notice)
  }
})

const turnLeft = computed(() => {
  const r = room.value
  if (!r || r.turnLeft == null) return null
  return Math.max(0, Math.ceil(r.turnLeft - (now.value - (r.receivedAt || now.value)) / 1000))
})

function newGame() {
  restart()
}

const player = (side) => room.value?.players?.[String(side)]

const status = computed(() => {
  const r = room.value
  if (!r) return { text: '', tone: 'muted' }
  if (r.winner) {
    if (r.winner === -1) {
      return { text: 'Ván cờ kết thúc: Hòa cờ (Lặp lại 3 lần)', tone: 'blue' }
    }
    const who = player(r.winner)
    const mine = r.winner === you.value
    const name = r.winner === 1 ? 'Đỏ' : 'Đen'
    return {
      text: you.value ? (mine ? 'Bạn thắng! 🎉' : `${who?.name ?? name} thắng!`)
                      : `${who?.name ?? name} thắng!`,
      tone: mine ? 'green' : 'red',
    }
  }
  if (r.botThinking) return { text: 'Bot cờ tướng đang tính toán…', tone: 'blue' }
  if (canPlay.value) return { text: 'Đến lượt bạn đi', tone: 'green' }
  const currentName = r.current === 1 ? 'Đỏ' : 'Đen'
  return { text: `Lượt của ${player(r.current)?.name ?? currentName}`, tone: 'muted' }
})

function onMovePiece(fr, fc, tr, tc) {
  movePiece(fr, fc, tr, tc)
}
</script>

<template>
  <div v-if="room" class="game-view">
    <!-- Thanh thông tin phòng -->
    <header class="room-bar">
      <div class="room-info">
        <span class="room-code">Phòng <strong>{{ room.code }}</strong></span>
        <span class="meta">Cờ Tướng · Đấu với máy ({{ room.levelName || 'Vừa' }})</span>
      </div>
      <button class="btn small" @click="leaveRoom">Rời phòng</button>
    </header>

    <!-- Thẻ hai người chơi -->
    <div class="players-bar">
      <!-- Đỏ -->
      <div class="player-card" :class="{
        active: room.current === 1 && playing,
        winner: room.winner === 1,
        isYou: you === 1
      }">
        <div class="piece-avatar red">🔴</div>
        <div class="player-meta">
          <div class="name-row">
            <strong>{{ player(1)?.name || 'Đỏ' }}</strong>
            <span v-if="you === 1" class="tag you">Bạn</span>
          </div>
          <div class="sub-row small muted">
            <span v-if="player(1)?.elo">{{ player(1).elo }} elo</span>
            <span v-else>Cầm quân Đỏ · đi trước</span>
          </div>
        </div>
      </div>

      <!-- Trung tâm: Trạng thái & Đồng hồ -->
      <div class="center-status">
        <div v-if="room.inCheck && playing" class="check-alert">
          ⚔️ CHIẾU TƯỚNG!
        </div>
        <div class="status-msg" :class="status.tone">{{ status.text }}</div>
        <div v-if="turnLeft != null && playing" class="turn-timer" :class="{ urgent: turnLeft <= 5 }">
          ⏱ {{ turnLeft }}s
        </div>
      </div>

      <!-- Đen -->
      <div class="player-card right" :class="{
        active: room.current === 2 && playing,
        winner: room.winner === 2,
        isYou: you === 2
      }">
        <div class="player-meta">
          <div class="name-row">
            <span v-if="you === 2" class="tag you">Bạn</span>
            <strong>{{ player(2)?.name || 'Đen' }}</strong>
          </div>
          <div class="sub-row small muted">
            <span v-if="player(2)?.elo">{{ player(2).elo }} elo</span>
            <span v-else>Cầm quân Đen · đi sau</span>
          </div>
        </div>
        <div class="piece-avatar black">⚫</div>
      </div>
    </div>

    <!-- Thông báo kết thúc ván nếu hòa -->
    <div v-if="room.winner === -1" class="draw-banner">
      ⚖️ {{ room.notice || 'Hai bên lặp lại thế cờ 3 lần, ván cờ hòa!' }}
    </div>

    <!-- Bàn cờ tướng -->
    <div class="board-wrapper">
      <XiangqiBoard :room="room" :can-play="canPlay" @move-piece="onMovePiece" />
    </div>

    <!-- Thanh công cụ điều khiển -->
    <div class="controls-bar">
      <div class="actions">
        <button class="btn" :disabled="!room.moves || room.botThinking || room.winner !== 0" @click="undo">
          Hoàn tác
        </button>
        <button class="btn green" @click="newGame">
          Ván mới
        </button>
      </div>

      <!-- Thống kê tính toán của bot -->
      <div v-if="room.stats && room.stats.nodes > 0" class="bot-stats muted small">
        <span>Độ sâu: <strong>{{ room.stats.depth }}</strong></span>
        <span>Số nút: <strong>{{ room.stats.nodes.toLocaleString() }}</strong></span>
        <span>Thời gian: <strong>{{ room.stats.elapsed }}s</strong></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 720px;
  margin: 0 auto;
}
.room-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.room-info { display: flex; align-items: baseline; gap: 10px; font-size: 0.95rem; }
.room-code { font-size: 1.15rem; color: var(--accent); }
.meta { color: var(--muted); font-size: 0.85rem; }

.players-bar {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  background: var(--card);
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
}
.player-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 8px;
  transition: background 0.15s, border-color 0.15s;
}
.player-card.right { justify-content: flex-end; text-align: right; }
.player-card.active {
  background: var(--bg);
  box-shadow: 0 0 0 2px var(--accent);
}
.player-card.winner {
  background: rgba(47, 174, 98, 0.15);
  box-shadow: 0 0 0 2px #2fae62;
}
.piece-avatar {
  font-size: 1.8rem;
  line-height: 1;
}
.player-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.name-row { display: flex; align-items: center; gap: 6px; }
.player-card.right .name-row { justify-content: flex-end; }
.tag {
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.tag.you { background: var(--accent); color: #fff; }

.center-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 170px;
  text-align: center;
}
.check-alert {
  background: #dc2626;
  color: #fff;
  font-weight: 800;
  font-size: 0.85rem;
  padding: 2px 10px;
  border-radius: 12px;
  letter-spacing: 1px;
  animation: pulse-alert 0.8s infinite alternate ease-in-out;
}
@keyframes pulse-alert {
  0% { transform: scale(0.95); opacity: 0.9; }
  100% { transform: scale(1.05); opacity: 1; }
}
.status-msg { font-size: 0.9rem; font-weight: 500; }
.status-msg.green { color: #2fae62; }
.status-msg.red { color: #e0786c; }
.status-msg.blue { color: #3b82f6; }
.turn-timer { font-size: 0.85rem; color: var(--muted); font-weight: 600; }
.turn-timer.urgent { color: #e0786c; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0.4; } }

.draw-banner {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid #3b82f6;
  color: #3b82f6;
  text-align: center;
  padding: 8px 12px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.95rem;
}

.board-wrapper {
  margin: 6px auto;
  width: 100%;
}

.controls-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  background: var(--card);
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
}
.actions { display: flex; gap: 10px; }
.bot-stats {
  display: flex;
  gap: 14px;
  font-size: 0.85rem;
}
</style>

