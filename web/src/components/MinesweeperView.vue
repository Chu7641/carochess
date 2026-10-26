<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, showError, state } from '../game.js'

const LEVELS = [
  { id: 'easy', name: 'Dễ', rows: 9, cols: 9, mines: 10 },
  { id: 'medium', name: 'Vừa', rows: 16, cols: 16, mines: 40 },
  { id: 'hard', name: 'Khó', rows: 16, cols: 30, mines: 99 },
]

const currentLevel = ref('easy')
const game = ref(null) // trạng thái ván từ máy chủ
const leaderboard = ref([])
const myBest = ref(null)
const flagMode = ref(false)
const isMouseDown = ref(false)

const displaySeconds = ref(0)
let timerInterval = null
let lastReceivedAt = 0
let serverElapsedMs = 0

let touchTimer = null
let didLongPress = false

const levelMeta = computed(() => LEVELS.find((l) => l.id === currentLevel.value) || LEVELS[0])
const levelName = computed(() => levelMeta.value.name)

const minesText = computed(() => {
  if (!game.value) return '010'
  const m = game.value.minesLeft
  if (m < 0) {
    return '-' + String(Math.min(99, Math.abs(m))).padStart(2, '0')
  }
  return String(Math.min(999, m)).padStart(3, '0')
})

const timerText = computed(() => {
  return String(Math.min(999, displaySeconds.value)).padStart(3, '0')
})

const faceEmoji = computed(() => {
  if (!game.value) return '🙂'
  if (game.value.state === 'won') return '😎'
  if (game.value.state === 'lost') return '😵'
  if (isMouseDown.value) return '😮'
  return '🙂'
})

function syncTimer(elapsedMs, isFinished) {
  serverElapsedMs = elapsedMs || 0
  lastReceivedAt = Date.now()
  displaySeconds.value = Math.floor(serverElapsedMs / 1000)

  clearInterval(timerInterval)
  if (!isFinished && game.value?.state === 'playing') {
    timerInterval = setInterval(() => {
      const now = Date.now()
      const totalMs = serverElapsedMs + (now - lastReceivedAt)
      displaySeconds.value = Math.floor(totalMs / 1000)
    }, 200)
  }
}

async function loadLeaderboard(lvl = currentLevel.value) {
  try {
    const res = await api(`/api/mines/leaderboard?level=${lvl}`)
    leaderboard.value = res.top || []
    myBest.value = res.me
  } catch {
    /* bỏ qua lỗi mạng */
  }
}

async function loadCurrentState() {
  try {
    const res = await api('/api/mines/state')
    if (res) {
      game.value = res
      currentLevel.value = res.level
      syncTimer(res.elapsedMs, res.state === 'won' || res.state === 'lost')
    } else {
      await newGame(currentLevel.value)
    }
  } catch (err) {
    showError(err.message || 'Không thể tải trạng thái ván.')
  }
  await loadLeaderboard(currentLevel.value)
}

async function newGame(lvl = currentLevel.value) {
  try {
    currentLevel.value = lvl
    const res = await api('/api/mines/new', { level: lvl })
    game.value = res
    syncTimer(0, false)
    await loadLeaderboard(lvl)
  } catch (err) {
    showError(err.message || 'Không thể tạo ván mới.')
  }
}

async function changeLevel(lvl) {
  if (lvl === currentLevel.value && game.value?.state === 'playing') return
  await newGame(lvl)
}

async function onReveal(r, c) {
  if (!game.value || game.value.state === 'won' || game.value.state === 'lost') return
  try {
    const res = await api('/api/mines/reveal', { r, c })
    game.value = res
    const isFinished = res.state === 'won' || res.state === 'lost'
    syncTimer(res.elapsedMs, isFinished)
    if (res.state === 'won') {
      await loadLeaderboard(currentLevel.value)
    }
  } catch (err) {
    showError(err.message || 'Lỗi khi mở ô.')
  }
}

async function onToggleFlag(r, c) {
  if (!game.value || game.value.state === 'won' || game.value.state === 'lost') return
  try {
    const res = await api('/api/mines/flag', { r, c })
    game.value = res
  } catch (err) {
    showError(err.message || 'Lỗi khi cắm cờ.')
  }
}

function onTouchStart(r, c) {
  didLongPress = false
  touchTimer = setTimeout(() => {
    didLongPress = true
    onToggleFlag(r, c)
  }, 400)
}

function onTouchEnd() {
  clearTimeout(touchTimer)
}

function onTouchMove() {
  clearTimeout(touchTimer)
}

function onCellClick(r, c) {
  if (didLongPress) {
    didLongPress = false
    return
  }
  if (flagMode.value) {
    onToggleFlag(r, c)
  } else {
    onReveal(r, c)
  }
}

function onCellRightClick(r, c) {
  onToggleFlag(r, c)
}

function onGridMouseDown(event) {
  if (event.button === 0) {
    isMouseDown.value = true
  }
}

function onGridMouseUp() {
  isMouseDown.value = false
}

onMounted(() => {
  loadCurrentState()
  window.addEventListener('mouseup', onGridMouseUp)
})

onUnmounted(() => {
  clearInterval(timerInterval)
  clearTimeout(touchTimer)
  window.removeEventListener('mouseup', onGridMouseUp)
})
</script>

<template>
  <section class="game">
    <!-- Khung bàn cờ bên trái -->
    <div class="board-wrap">
      <div class="mines-frame" @mousedown="onGridMouseDown">
        <!-- Thanh tiêu đề bảng điều khiển Windows cổ điển -->
        <div class="mines-header">
          <!-- Bộ đếm mìn còn lại -->
          <div class="digital-display" title="Số mìn còn lại">{{ minesText }}</div>
          <!-- Nút mặt cười khởi tạo ván mới -->
          <button class="face-btn" title="Ván mới" @click="newGame(currentLevel)">
            {{ faceEmoji }}
          </button>
          <!-- Đồng hồ thời gian -->
          <div class="digital-display" title="Thời gian">{{ timerText }}</div>
        </div>

        <!-- Lưới ô dò mìn -->
        <div v-if="game" class="mines-grid-wrap">
          <div class="mines-grid" :class="`grid-${game.level}`">
            <template v-for="(row, r) in game.cells" :key="`r-${r}`">
              <div
                v-for="(val, c) in row"
                :key="`c-${r}-${c}`"
                class="cell"
                :class="{
                  unrevealed: val === 'h' || val === 'f',
                  revealed: typeof val === 'number' || val === 'm' || val === 'w',
                  exploded: val === 'x',
                  [`num-${val}`]: typeof val === 'number' && val > 0,
                }"
                @click="onCellClick(r, c)"
                @contextmenu.prevent="onCellRightClick(r, c)"
                @touchstart="onTouchStart(r, c)"
                @touchend="onTouchEnd"
                @touchmove="onTouchMove"
              >
                <template v-if="val === 'f'">🚩</template>
                <template v-else-if="val === 'x'">💣</template>
                <template v-else-if="val === 'm'">💣</template>
                <template v-else-if="val === 'w'">❌</template>
                <template v-else-if="typeof val === 'number' && val > 0">{{ val }}</template>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Thanh bên phải hiển thị cấu hình, trạng thái và bảng xếp hạng -->
    <aside class="card side">
      <!-- Chọn độ khó -->
      <div class="field">
        <label class="label">Độ khó</label>
        <div class="segmented">
          <button
            v-for="lvl in LEVELS"
            :key="lvl.id"
            class="seg-btn"
            :class="{ active: currentLevel === lvl.id }"
            @click="changeLevel(lvl.id)"
          >
            {{ lvl.name }}
          </button>
        </div>
      </div>

      <!-- Nút bắt đầu ván mới -->
      <button class="btn green block" @click="newGame(currentLevel)">🔄 Ván mới</button>

      <!-- Nút bật/tắt chế độ cắm cờ cho điện thoại -->
      <button
        class="btn block"
        :class="{ blue: flagMode }"
        @click="flagMode = !flagMode"
      >
        🚩 Chế độ cắm cờ: {{ flagMode ? 'BẬT' : 'TẮT' }}
      </button>

      <!-- Kết quả ván cờ -->
      <div v-if="game && game.state === 'won'" class="result-banner win">
        <strong>🎉 Bạn đã chiến thắng!</strong>
        <span>Hoàn thành trong {{ (game.elapsedMs / 1000).toFixed(3) }} giây</span>
        <span v-if="game.newRecord" class="record-badge">🏆 Kỷ lục mới!</span>
      </div>
      <div v-else-if="game && game.state === 'lost'" class="result-banner lose">
        <strong>💥 Nổ mìn! Bạn đã thua.</strong>
        <span class="small muted">Bấm 🙂 hoặc "Ván mới" để thử lại</span>
      </div>

      <!-- Kỷ lục cá nhân của người dùng -->
      <div v-if="myBest" class="best-card">
        <span class="small muted">Thành tích tốt nhất ({{ levelName }}):</span>
        <div class="best-row">
          <strong>{{ (myBest.ms / 1000).toFixed(3) }}s</strong>
          <span class="rank-badge">Hạng #{{ myBest.rank }}</span>
        </div>
      </div>

      <!-- Bảng xếp hạng -->
      <div class="leaderboard-section">
        <h3 class="leaderboard-title">Bảng xếp hạng ({{ levelName }})</h3>
        <ul v-if="leaderboard.length" class="leaderboard-list">
          <li
            v-for="item in leaderboard"
            :key="`${item.username}-${item.rank}`"
            class="leaderboard-item"
            :class="{ me: item.username === state.user?.username }"
          >
            <span class="rank">#{{ item.rank }}</span>
            <span class="pname">
              {{ item.username }}
              <em v-if="item.username === state.user?.username" class="small muted">(bạn)</em>
            </span>
            <span class="score">{{ (item.ms / 1000).toFixed(3) }}s</span>
          </li>
        </ul>
        <p v-else class="small muted empty-note">Chưa có kỷ lục nào tại mức này.</p>
      </div>
    </aside>
  </section>
</template>

<style scoped>
.game {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: start;
}
.board-wrap {
  min-width: 0;
  width: 100%;
  overflow-x: auto;
  display: flex;
  justify-content: safe center; /* bàn rộng hơn khung: vẫn cuộn được tới mép trái */
  padding: 4px 0;
}
.side {
  display: grid;
  gap: 14px;
  position: sticky;
  top: 16px;
}

/* Khung bàn cổ điển Windows */
.mines-frame {
  display: inline-block;
  background: #c0c0c0;
  border-top: 3px solid #ffffff;
  border-left: 3px solid #ffffff;
  border-right: 3px solid #7b7b7b;
  border-bottom: 3px solid #7b7b7b;
  padding: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}
.mines-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  background: #c0c0c0;
  border-top: 2.5px solid #7b7b7b;
  border-left: 2.5px solid #7b7b7b;
  border-right: 2.5px solid #ffffff;
  border-bottom: 2.5px solid #ffffff;
  margin-bottom: 8px;
}
.digital-display {
  background: #000000;
  color: #ff0000;
  font-family: "Consolas", "Courier New", monospace;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: 2px;
  line-height: 1;
  padding: 4px 6px;
  border-top: 2px solid #7b7b7b;
  border-left: 2px solid #7b7b7b;
  border-right: 2px solid #ffffff;
  border-bottom: 2px solid #ffffff;
  user-select: none;
  font-variant-numeric: tabular-nums;
  min-width: 54px;
  text-align: center;
}
.face-btn {
  width: 36px;
  height: 36px;
  background: #c0c0c0;
  border-top: 2.5px solid #ffffff;
  border-left: 2.5px solid #ffffff;
  border-right: 2.5px solid #7b7b7b;
  border-bottom: 2.5px solid #7b7b7b;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.35rem;
  cursor: pointer;
  user-select: none;
  border-radius: 2px;
}
.face-btn:active {
  border-top: 2.5px solid #7b7b7b;
  border-left: 2.5px solid #7b7b7b;
  border-right: 2.5px solid #ffffff;
  border-bottom: 2.5px solid #ffffff;
}

/* Lưới các ô */
.mines-grid-wrap {
  border-top: 3px solid #7b7b7b;
  border-left: 3px solid #7b7b7b;
  border-right: 3px solid #ffffff;
  border-bottom: 3px solid #ffffff;
  background: #7b7b7b;
  display: inline-block;
}
.mines-grid {
  display: grid;
  user-select: none;
  background: #bdbdbd;
  /* Hàng cao cố định bằng ô: emoji 🚩/💣 cao hơn chữ số không được làm giãn hàng */
  grid-auto-rows: var(--cell);
}
.grid-easy { --cell: 44px; grid-template-columns: repeat(9, var(--cell)); }
.grid-medium { --cell: 36px; grid-template-columns: repeat(16, var(--cell)); }
.grid-hard { --cell: 28px; grid-template-columns: repeat(30, var(--cell)); }

.cell {
  width: var(--cell);
  height: var(--cell);
  overflow: hidden;
  line-height: 1;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: Arial, sans-serif;
  font-weight: 700;
  user-select: none;
  cursor: pointer;
  font-size: calc(var(--cell) * 0.55);
}
.cell.unrevealed {
  background: #c0c0c0;
  border-top: 2.5px solid #ffffff;
  border-left: 2.5px solid #ffffff;
  border-right: 2.5px solid #7b7b7b;
  border-bottom: 2.5px solid #7b7b7b;
}
.cell.unrevealed:active {
  border-top: 2.5px solid #7b7b7b;
  border-left: 2.5px solid #7b7b7b;
  border-right: 2.5px solid #ffffff;
  border-bottom: 2.5px solid #ffffff;
}
.cell.revealed {
  background: #bdbdbd;
  border: 1px solid #7b7b7b;
}
.cell.exploded {
  background: #ff0000;
  border: 1px solid #7b7b7b;
}

/* Màu số chuẩn Minesweeper */
.num-1 { color: #0000ff; }
.num-2 { color: #008000; }
.num-3 { color: #ff0000; }
.num-4 { color: #000080; }
.num-5 { color: #800000; }
.num-6 { color: #008080; }
.num-7 { color: #000000; }
.num-8 { color: #808080; }

/* Thông báo kết quả */
.result-banner {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid var(--panel-border);
}
.result-banner.win {
  background: rgba(47, 174, 98, 0.15);
  border-color: #2fae62;
  color: var(--text);
}
.result-banner.lose {
  background: rgba(224, 120, 108, 0.15);
  border-color: #e0786c;
  color: var(--text);
}
.record-badge {
  font-weight: 700;
  color: #2fae62;
}

/* Thẻ kỷ lục cá nhân */
.best-card {
  display: grid;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bg);
  border: 1px solid var(--panel-border);
}
.best-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.rank-badge {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--accent);
}

/* Danh sách bảng xếp hạng */
.leaderboard-section {
  display: grid;
  gap: 8px;
}
.leaderboard-title {
  margin: 0;
  font-size: 1rem;
}
.leaderboard-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
  max-height: 280px;
  overflow-y: auto;
}
.leaderboard-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--panel-border);
  font-size: 0.9rem;
}
.leaderboard-item.me {
  border-color: var(--accent);
  background: rgba(238, 182, 61, 0.12);
  font-weight: 600;
}
.leaderboard-item .rank {
  font-weight: 700;
  color: var(--muted);
  width: 28px;
}
.leaderboard-item .pname {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.leaderboard-item .score {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.empty-note {
  margin: 0;
  font-style: italic;
}

@media (max-width: 860px) {
  .game {
    grid-template-columns: 1fr;
  }
  .side {
    position: static;
  }
}
@media (max-width: 560px) {
  .grid-easy { --cell: 34px; }
  .grid-medium { --cell: 30px; }
}
</style>

