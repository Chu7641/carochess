<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, showError, state } from '../game.js'

const LEVELS = [
  { id: 'easy', name: 'Dễ' },
  { id: 'medium', name: 'Vừa' },
  { id: 'hard', name: 'Khó' },
]

const currentLevel = ref('easy')
const game = ref(null) // Trạng thái ván cờ từ máy chủ
const selectedCell = ref({ r: 0, c: 0 })
const noteMode = ref(false)
const notes = ref(Array.from({ length: 9 }, () => Array.from({ length: 9 }, () => [])))
const leaderboard = ref([])
const myBest = ref(null)

const displayMs = ref(0)
let timerInterval = null
let lastReceivedAt = 0
let serverElapsedMs = 0

const levelMeta = computed(() => LEVELS.find((l) => l.id === currentLevel.value) || LEVELS[0])
const levelName = computed(() => levelMeta.value.name)

const conflictsSet = computed(() => {
  const set = new Set()
  if (game.value?.conflicts) {
    for (const [r, c] of game.value.conflicts) {
      set.add(`${r},${c}`)
    }
  }
  return set
})

const selectedVal = computed(() => {
  if (!game.value?.grid) return 0
  const { r, c } = selectedCell.value
  return game.value.grid[r]?.[c] || 0
})

function formatRunningTime(ms) {
  const totalSec = Math.floor(ms / 1000)
  const mins = Math.floor(totalSec / 60)
  const secs = totalSec % 60
  return `${mins}:${String(secs).padStart(2, '0')}`
}

function formatFinalTime(ms) {
  const mins = Math.floor(ms / 60000)
  const secs = Math.floor((ms % 60000) / 1000)
  const millis = ms % 1000
  if (mins > 0) {
    return `${mins}:${String(secs).padStart(2, '0')},${String(millis).padStart(3, '0')}`
  }
  return `${secs},${String(millis).padStart(3, '0')}s`
}

function syncTimer(elapsedMs, isFinished) {
  serverElapsedMs = elapsedMs || 0
  lastReceivedAt = Date.now()
  displayMs.value = serverElapsedMs

  clearInterval(timerInterval)
  if (!isFinished) {
    timerInterval = setInterval(() => {
      const now = Date.now()
      displayMs.value = serverElapsedMs + (now - lastReceivedAt)
    }, 200)
  }
}

// ---------- Ghi chú (Notes - lưu client) ----------
const storageKey = computed(() => `sudoku.notes.${state.user?.id || 'guest'}.${currentLevel.value}`)

function loadNotes() {
  try {
    const raw = localStorage.getItem(storageKey.value)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length === 9) {
        notes.value = parsed
        return
      }
    }
  } catch {
    /* bỏ qua lỗi localStorage */
  }
  clearAllNotes()
}

function saveNotes() {
  try {
    localStorage.setItem(storageKey.value, JSON.stringify(notes.value))
  } catch {
    /* bỏ qua lỗi */
  }
}

function clearAllNotes() {
  notes.value = Array.from({ length: 9 }, () => Array.from({ length: 9 }, () => []))
  saveNotes()
}

function hasNote(r, c, num) {
  return notes.value[r]?.[c]?.includes(num)
}

function toggleNote(r, c, num) {
  const list = notes.value[r][c] || []
  const idx = list.indexOf(num)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push(num)
  }
  notes.value[r][c] = list
  saveNotes()
}

function removeRelatedNotes(r, c, num) {
  notes.value[r][c] = []
  const startR = Math.floor(r / 3) * 3
  const startC = Math.floor(c / 3) * 3
  for (let i = 0; i < 9; i++) {
    // Xóa trong hàng
    const rowList = notes.value[r][i]
    if (rowList) {
      const idx = rowList.indexOf(num)
      if (idx >= 0) rowList.splice(idx, 1)
    }
    // Xóa trong cột
    const colList = notes.value[i][c]
    if (colList) {
      const idx = colList.indexOf(num)
      if (idx >= 0) colList.splice(idx, 1)
    }
  }
  // Xóa trong khối 3x3
  for (let br = startR; br < startR + 3; br++) {
    for (let bc = startC; bc < startC + 3; bc++) {
      const boxList = notes.value[br][bc]
      if (boxList) {
        const idx = boxList.indexOf(num)
        if (idx >= 0) boxList.splice(idx, 1)
      }
    }
  }
  saveNotes()
}

// ---------- API máy chủ ----------
async function loadLeaderboard(lvl = currentLevel.value) {
  try {
    const res = await api(`/api/sudoku/leaderboard?level=${lvl}`)
    leaderboard.value = res.top || []
    myBest.value = res.me
  } catch {
    /* bỏ qua lỗi mạng */
  }
}

async function loadCurrentState() {
  try {
    const res = await api('/api/sudoku/state')
    if (res) {
      game.value = res
      currentLevel.value = res.level
      syncTimer(res.elapsedMs, res.solved)
      loadNotes()
    } else {
      await newGame(currentLevel.value)
    }
  } catch (err) {
    showError(err.message || 'Không thể tải trạng thái ván Sudoku.')
  }
  await loadLeaderboard(currentLevel.value)
}

async function newGame(lvl = currentLevel.value) {
  try {
    currentLevel.value = lvl
    clearAllNotes()
    const res = await api('/api/sudoku/new', { level: lvl })
    game.value = res
    syncTimer(0, false)
    selectedCell.value = { r: 0, c: 0 }
    loadNotes()
    await loadLeaderboard(lvl)
  } catch (err) {
    showError(err.message || 'Không thể tạo ván Sudoku mới.')
  }
}

async function changeLevel(lvl) {
  if (lvl === currentLevel.value) return
  if (game.value && !game.value.solved) {
    if (!confirm('Ván chơi chưa hoàn thành. Đổi mức độ sẽ bắt đầu một ván mới. Bạn chắc chắn?')) {
      return
    }
  }
  await newGame(lvl)
}

async function handleSetCell(r, c, v) {
  if (!game.value || game.value.solved) return
  if (game.value.given[r][c]) return

  try {
    const res = await api('/api/sudoku/set', { r, c, v })
    game.value = res
    syncTimer(res.elapsedMs, res.solved)
    if (v > 0) {
      removeRelatedNotes(r, c, v)
    }
    if (res.solved) {
      await loadLeaderboard(currentLevel.value)
    }
  } catch (err) {
    showError(err.message || 'Lỗi khi điền số.')
  }
}

async function handleHint() {
  if (!game.value || game.value.solved) return
  try {
    const res = await api('/api/sudoku/hint', {})
    game.value = res
    syncTimer(res.elapsedMs, res.solved)
    if (res.solved) {
      await loadLeaderboard(currentLevel.value)
    }
  } catch (err) {
    showError(err.message || 'Lỗi khi lấy gợi ý.')
  }
}

// ---------- Thao tác người dùng ----------
function selectCell(r, c) {
  selectedCell.value = { r, c }
}

function handleInputNumber(num) {
  if (!game.value || game.value.solved) return
  const { r, c } = selectedCell.value
  if (game.value.given[r][c]) return

  if (noteMode.value) {
    toggleNote(r, c, num)
  } else {
    handleSetCell(r, c, num)
  }
}

function handleErase() {
  if (!game.value || game.value.solved) return
  const { r, c } = selectedCell.value
  if (game.value.given[r][c]) return

  if (game.value.grid[r][c] !== 0) {
    handleSetCell(r, c, 0)
  } else if (notes.value[r]?.[c]?.length > 0) {
    notes.value[r][c] = []
    saveNotes()
  }
}

function toggleNoteMode() {
  noteMode.value = !noteMode.value
}

function onKeyDown(event) {
  if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') return
  const { r, c } = selectedCell.value

  if (event.key >= '1' && event.key <= '9') {
    event.preventDefault()
    handleInputNumber(parseInt(event.key, 10))
  } else if (event.key === 'Backspace' || event.key === 'Delete' || event.key === '0') {
    event.preventDefault()
    handleErase()
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    selectedCell.value = { r: Math.max(0, r - 1), c }
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    selectedCell.value = { r: Math.min(8, r + 1), c }
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    selectedCell.value = { r, c: Math.max(0, c - 1) }
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    selectedCell.value = { r, c: Math.min(8, c + 1) }
  } else if (event.key === 'n' || event.key === 'N') {
    event.preventDefault()
    toggleNoteMode()
  }
}

onMounted(() => {
  loadCurrentState()
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  clearInterval(timerInterval)
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <section class="game">
    <!-- Khung bàn cờ bên trái -->
    <div class="board-wrap">
      <div class="sudoku-container">
        <!-- Lưới bàn cờ 9x9 -->
        <div v-if="game" class="sudoku-grid" role="grid" aria-label="Bàn cờ Sudoku">
          <template v-for="(row, r) in game.grid" :key="`r-${r}`">
            <div
              v-for="(val, c) in row"
              :key="`c-${r}-${c}`"
              class="cell"
              :class="{
                given: game.given[r][c],
                'user-filled': !game.given[r][c] && val > 0,
                selected: selectedCell.r === r && selectedCell.c === c,
                peer: (selectedCell.r === r || selectedCell.c === c ||
                       (Math.floor(selectedCell.r / 3) === Math.floor(r / 3) &&
                        Math.floor(selectedCell.c / 3) === Math.floor(c / 3))) &&
                      !(selectedCell.r === r && selectedCell.c === c),
                'same-val': selectedVal > 0 && val === selectedVal && !(selectedCell.r === r && selectedCell.c === c),
                conflict: conflictsSet.has(`${r},${c}`),
                'box-right': c === 2 || c === 5,
                'box-bottom': r === 2 || r === 5,
                'no-border-right': c === 8,
                'no-border-bottom': r === 8,
              }"
              @click="selectCell(r, c)"
            >
              <!-- Số chính thức trong ô -->
              <span v-if="val > 0" class="cell-val">{{ val }}</span>
              <!-- Lưới ghi chú con khi ô trống -->
              <div v-else-if="notes[r]?.[c]?.length" class="notes-grid">
                <span v-for="n in 9" :key="n" class="note-num">
                  {{ hasNote(r, c, n) ? n : '' }}
                </span>
              </div>
            </div>
          </template>
        </div>

        <!-- Bàn phím số & công cụ bên dưới bàn -->
        <div class="keypad-wrap">
          <div class="digits-row">
            <button
              v-for="n in 9"
              :key="n"
              class="btn digit-btn"
              @click="handleInputNumber(n)"
            >
              {{ n }}
            </button>
          </div>
          <div class="tools-row">
            <button
              class="btn"
              :class="{ blue: noteMode }"
              @click="toggleNoteMode"
            >
              ✏️ Ghi chú: {{ noteMode ? 'BẬT' : 'TẮT' }} (N)
            </button>
            <button class="btn" @click="handleErase">⌫ Xóa</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Thanh bên phải hiển thị cấu hình, trạng thái và bảng xếp hạng -->
    <aside class="card side">
      <!-- Trạng thái & Đồng hồ -->
      <div class="status-header">
        <div class="status-title" :class="{ win: game?.solved }">
          {{ game?.solved ? '🎉 Hoàn thành!' : 'Đang giải Sudoku' }}
        </div>
        <div class="timer-display" title="Thời gian">
          ⏱ {{ formatRunningTime(displayMs) }}
        </div>
      </div>

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

      <!-- Thông tin gợi ý & các nút hành động -->
      <div class="hints-info small muted">
        <span>Số gợi ý đã dùng: <strong>{{ game?.hints || 0 }}</strong></span>
      </div>

      <button
        class="btn blue block"
        :disabled="!game || game.solved"
        @click="handleHint"
      >
        💡 Gợi ý (+30 giây phạt)
      </button>

      <button class="btn green block" @click="newGame(currentLevel)">
        🔄 Ván mới
      </button>

      <!-- Kết quả khi giải xong -->
      <div v-if="game && game.solved" class="result-banner win">
        <strong>🎉 Chúc mừng bạn đã giải xong!</strong>
        <span>Hoàn thành trong {{ formatFinalTime(game.elapsedMs) }}</span>
        <span v-if="game.newRecord" class="record-badge">🏆 Kỷ lục mới!</span>
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
  display: flex;
  justify-content: center;
  padding: 4px 0;
}
.side {
  display: grid;
  gap: 14px;
  position: sticky;
  top: 16px;
}

/* Khung bàn cờ Sudoku */
.sudoku-container {
  width: 100%;
  max-width: 520px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sudoku-grid {
  display: grid;
  grid-template-columns: repeat(9, 1fr);
  grid-template-rows: repeat(9, 1fr);
  grid-auto-rows: 1fr;
  aspect-ratio: 1 / 1;
  width: 100%;
  max-height: calc(100vh - 200px);
  max-width: calc(100vh - 200px); /* chặn cả rộng: màn thấp thì bàn vẫn vuông, không bị bẹt */
  margin: 0 auto;
  border: 2.5px solid var(--text);
  border-radius: var(--radius);
  background: var(--panel);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.cell {
  min-width: 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  user-select: none;
  cursor: pointer;
  background: var(--panel);
  font-family: inherit;
  font-size: clamp(1.2rem, 3.2vw, 1.8rem);
  border-right: 1px solid var(--panel-border);
  border-bottom: 1px solid var(--panel-border);
  transition: background-color 0.1s ease;
}

/* Phân cách khối 3x3 */
.cell.box-right {
  border-right: 2.5px solid var(--text);
}
.cell.box-bottom {
  border-bottom: 2.5px solid var(--text);
}
.cell.no-border-right {
  border-right: none;
}
.cell.no-border-bottom {
  border-bottom: none;
}

/* Màu số */
.cell.given {
  font-weight: 700;
  color: var(--text);
}
.cell.user-filled {
  font-weight: 600;
  color: var(--blue);
}

/* Đánh dấu chọn & liên quan */
.cell.peer {
  background: rgba(238, 182, 61, 0.12);
}
.cell.same-val {
  background: rgba(238, 182, 61, 0.24);
}
.cell.selected {
  background: rgba(238, 182, 61, 0.42);
  box-shadow: 0 0 0 2px var(--accent) inset;
}
.cell.conflict {
  color: var(--red) !important;
  background: rgba(184, 72, 62, 0.22) !important;
}

.cell-val {
  line-height: 1;
}

/* Lưới ghi chú con */
.notes-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, 1fr);
  width: 100%;
  height: 100%;
  pointer-events: none;
  padding: 2px;
  box-sizing: border-box;
}
.note-num {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: clamp(0.55rem, 1.1vw, 0.75rem);
  color: var(--muted);
  font-weight: 600;
  line-height: 1;
}

/* Bàn phím số & công cụ */
.keypad-wrap {
  display: grid;
  gap: 8px;
}
.digits-row {
  display: grid;
  grid-template-columns: repeat(9, 1fr);
  gap: 6px;
}
.digit-btn {
  padding: 10px 0;
  font-size: 1.15rem;
  font-weight: 700;
  text-align: center;
}
.tools-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 8px;
}

/* Thanh bên trạng thái & thông tin */
.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--panel-border);
}
.status-title {
  font-size: 1.1rem;
  font-weight: 700;
}
.status-title.win {
  color: var(--green);
}
.timer-display {
  font-size: 1.15rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text);
}

.hints-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

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

/* Bảng xếp hạng */
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
</style>

