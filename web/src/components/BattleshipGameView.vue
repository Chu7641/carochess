<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  fire,
  leaveRoom,
  placeRandom,
  placeShips,
  restart,
  showError,
  state,
} from '../game.js'

const SHIP_DEFS = [
  { name: 'Tàu sân bay', len: 5 },
  { name: 'Thiết giáp hạm', len: 4 },
  { name: 'Tuần dương hạm', len: 3 },
  { name: 'Tàu ngầm', len: 3 },
  { name: 'Khu trục hạm', len: 2 },
]

const COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
const ROWS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

const room = computed(() => state.room)
const you = computed(() => room.value?.you)
const isBot = computed(() => room.value?.mode === 'bot')
const phase = computed(() => room.value?.phase)
const myFleet = computed(() => room.value?.myFleet)
const opponentBoard = computed(() => room.value?.opponentBoard)
const lastShot = computed(() => room.value?.lastShot)

const canShoot = computed(() =>
  phase.value === 'playing' &&
  you.value === room.value?.current &&
  (!isBot.value || !room.value?.botThinking)
)

// Trạng thái xếp tàu thủ công
const placedShips = ref([])
const selectedDefIndex = ref(0)
const isVertical = ref(false)
const hoverPos = ref(null)

const unplacedDefs = computed(() => {
  const placedNames = new Set(placedShips.value.map((s) => s.name))
  return SHIP_DEFS.filter((d) => !placedNames.has(d.name))
})

const selectedShipDef = computed(() => {
  if (unplacedDefs.value.length === 0) return null
  const found = unplacedDefs.value.find((_, idx) => idx === selectedDefIndex.value)
  return found || unplacedDefs.value[0] || null
})

function selectShip(def) {
  const idx = unplacedDefs.value.findIndex((d) => d.name === def.name)
  if (idx !== -1) selectedDefIndex.value = idx
}

function toggleOrientation() {
  isVertical.value = !isVertical.value
}

function handleKeydown(e) {
  if (e.key === 'r' || e.key === 'R') {
    toggleOrientation()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

watch(() => room.value?.notice, (notice) => {
  if (notice && !notice.includes('Trúng') && !notice.includes('Đánh chìm') && !notice.includes('Trượt') && !notice.includes('bắt đầu')) {
    showError(notice)
  }
})

// Khi phase đổi về placing (ví dụ restart ván mới)
watch(phase, (newPhase) => {
  if (newPhase === 'placing') {
    placedShips.value = []
    selectedDefIndex.value = 0
    hoverPos.value = null
  }
})

// Kiểm tra vị trí đặt tàu có hợp lệ không
function getShipCells(r, c, len, vertical) {
  const cells = []
  for (let i = 0; i < len; i++) {
    cells.push({
      r: vertical ? r + i : r,
      c: vertical ? c : c + i,
    })
  }
  return cells
}

function isPlacementValid(r, c, len, vertical) {
  const cells = getShipCells(r, c, len, vertical)
  for (const cell of cells) {
    if (cell.r < 0 || cell.r >= 10 || cell.c < 0 || cell.c >= 10) {
      return false
    }
  }
  // Kiểm tra trùng với các tàu đã đặt
  for (const ship of placedShips.value) {
    const existingCells = getShipCells(ship.r, ship.c, ship.len, ship.vertical)
    for (const ec of existingCells) {
      for (const nc of cells) {
        if (ec.r === nc.r && ec.c === nc.c) {
          return false
        }
      }
    }
  }
  return true
}

const previewCells = computed(() => {
  if (!hoverPos.value || !selectedShipDef.value || phase.value !== 'placing') {
    return []
  }
  const { r, c } = hoverPos.value
  const len = selectedShipDef.value.len
  const vertical = isVertical.value
  const valid = isPlacementValid(r, c, len, vertical)
  const cells = getShipCells(r, c, len, vertical)
  return cells.map((cell) => ({
    r: cell.r,
    c: cell.c,
    valid,
    inBounds: cell.r >= 0 && cell.r < 10 && cell.c >= 0 && cell.c < 10,
  }))
})

function isCellInPreview(r, c) {
  return previewCells.value.find((cell) => cell.r === r && cell.c === c)
}

function getPlacedShipAt(r, c) {
  for (const ship of placedShips.value) {
    const cells = getShipCells(ship.r, ship.c, ship.len, ship.vertical)
    if (cells.some((cell) => cell.r === r && cell.c === c)) {
      return ship
    }
  }
  return null
}

function onPlaceBoardClick(r, c) {
  if (phase.value !== 'placing') return
  // Nếu nhấn vào tàu đã đặt -> gỡ tàu ra để đặt lại
  const existingShip = getPlacedShipAt(r, c)
  if (existingShip) {
    placedShips.value = placedShips.value.filter((s) => s.name !== existingShip.name)
    const def = SHIP_DEFS.find((d) => d.name === existingShip.name)
    if (def) selectShip(def)
    return
  }

  // Nếu có tàu đang chọn -> thử đặt
  if (selectedShipDef.value) {
    const len = selectedShipDef.value.len
    const vertical = isVertical.value
    if (isPlacementValid(r, c, len, vertical)) {
      placedShips.value.push({
        name: selectedShipDef.value.name,
        len,
        r,
        c,
        vertical,
      })
      selectedDefIndex.value = 0
    }
  }
}

function removePlacedShip(shipName) {
  placedShips.value = placedShips.value.filter((s) => s.name !== shipName)
  const def = SHIP_DEFS.find((d) => d.name === shipName)
  if (def) selectShip(def)
}

function resetPlacement() {
  placedShips.value = []
  selectedDefIndex.value = 0
}

function confirmPlacement() {
  if (placedShips.value.length !== 5) return
  placeShips(placedShips.value)
}

function handleAutoPlace() {
  placeRandom()
}

// Bắn vào ô đối phương
function onOpponentCellClick(r, c) {
  if (!canShoot.value) return
  if (isOpponentShot(r, c)) return
  fire(r, c)
}

function isOpponentShot(r, c) {
  if (!opponentBoard.value) return false
  const inHits = opponentBoard.value.hits?.some(([hr, hc]) => hr === r && hc === c)
  const inMisses = opponentBoard.value.misses?.some(([mr, mc]) => mr === r && mc === c)
  return inHits || inMisses
}

function getOpponentCellState(r, c) {
  if (!opponentBoard.value) return null
  const isHit = opponentBoard.value.hits?.some(([hr, hc]) => hr === r && hc === c)
  const isMiss = opponentBoard.value.misses?.some(([mr, mc]) => mr === r && mc === c)
  let isSunk = false
  if (opponentBoard.value.sunkShips) {
    for (const ship of opponentBoard.value.sunkShips) {
      if (ship.cells?.some(([sr, sc]) => sr === r && sc === c)) {
        isSunk = true
        break
      }
    }
  }
  let isRevealed = false
  if (opponentBoard.value.revealedShips) {
    for (const ship of opponentBoard.value.revealedShips) {
      if (ship.cells?.some(([sr, sc]) => sr === r && sc === c)) {
        isRevealed = true
        break
      }
    }
  }
  return { isHit, isMiss, isSunk, isRevealed }
}

function getMyCellState(r, c) {
  let hasShip = false
  let isSunk = false
  if (myFleet.value?.ships) {
    for (const ship of myFleet.value.ships) {
      if (ship.cells?.some(([sr, sc]) => sr === r && sc === c)) {
        hasShip = true
        break
      }
    }
    if (myFleet.value.sunkShips) {
      for (const ship of myFleet.value.sunkShips) {
        if (ship.cells?.some(([sr, sc]) => sr === r && sc === c)) {
          isSunk = true
          break
        }
      }
    }
  } else if (placedShips.value.length) {
    hasShip = !!getPlacedShipAt(r, c)
  }

  const isHit = myFleet.value?.hits?.some(([hr, hc]) => hr === r && hc === c)
  const isMiss = myFleet.value?.misses?.some(([mr, mc]) => mr === r && mc === c)

  return { hasShip, isHit, isMiss, isSunk }
}

// Thống kê bắn của người chơi
const playerStats = computed(() => {
  if (!opponentBoard.value) return { shots: 0, hits: 0, accuracy: 0 }
  const hits = opponentBoard.value.hits?.length || 0
  const misses = opponentBoard.value.misses?.length || 0
  const shots = hits + misses
  const accuracy = shots > 0 ? Math.round((hits / shots) * 100) : 0
  return { shots, hits, accuracy }
})

const myShipsList = computed(() => {
  if (room.value?.shipsLeft && you.value) {
    return room.value.shipsLeft[String(you.value)] || []
  }
  return []
})

const opponentShipsList = computed(() => {
  if (room.value?.shipsLeft && you.value) {
    return room.value.shipsLeft[String(3 - you.value)] || []
  }
  return []
})

const status = computed(() => {
  const r = room.value
  if (!r) return { text: '', tone: 'muted' }
  if (r.winner) {
    const mine = r.winner === you.value
    return {
      text: mine ? 'Bạn toàn thắng! 🎉 Tiêu diệt hạm đội địch' : 'Thất trận! Hạm đội của bạn đã chìm',
      tone: mine ? 'green' : 'red',
    }
  }
  if (phase.value === 'placing') {
    return {
      text: 'Giai đoạn dàn quân: Xếp 5 tàu vào vị trí',
      tone: 'blue',
    }
  }
  if (r.botThinking) {
    return { text: 'Bot đang ngắm bắn…', tone: 'blue' }
  }
  if (canShoot.value) {
    return { text: 'Lượt của bạn — Khai hỏa!', tone: 'green' }
  }
  return { text: 'Lượt đối phương khai hỏa…', tone: 'muted' }
})

function handleNewGame() {
  restart()
}

function handleLeave() {
  leaveRoom()
}
</script>

<template>
  <section v-if="room" class="game">
    <div class="board-wrap">
      <!-- GIAI ĐOẠN 1: DÀN QUÂN / XẾP TÀU -->
      <div v-if="phase === 'placing'" class="placing-container card">
        <div class="placing-header">
          <div class="placing-title">
            <h3>⚓ Bố trí hạm đội hải chiến</h3>
            <p class="small muted">
              Nhấn ô để đặt tàu. Nhấn tàu đã đặt để gỡ ra. Phím <kbd>R</kbd> hoặc nút xoay để đổi hướng. Tàu được phép nằm sát nhau.
            </p>
          </div>
          <div class="placing-actions">
            <button class="btn" @click="toggleOrientation">
              {{ isVertical ? '↕ Dọc' : '↔ Ngang' }} (Phím R)
            </button>
            <button class="btn blue" @click="handleAutoPlace">
              🎲 Xếp ngẫu nhiên
            </button>
            <button class="btn" :disabled="!placedShips.length" @click="resetPlacement">
              Làm lại
            </button>
            <button class="btn green" :disabled="placedShips.length !== 5" @click="confirmPlacement">
              ✓ Xác nhận vào trận ({{ placedShips.length }}/5)
            </button>
          </div>
        </div>

        <div class="placing-body">
          <!-- Bàn cờ đặt tàu 10x10 -->
          <div class="sea-board-wrapper">
            <div class="sea-board">
              <!-- Hàng nhãn cột A-J -->
              <div class="sea-corner"></div>
              <div v-for="col in COLS" :key="col" class="sea-header-col">{{ col }}</div>

              <!-- 10 Hàng -->
              <template v-for="(rowNum, r) in ROWS" :key="rowNum">
                <div class="sea-header-row">{{ rowNum }}</div>
                <div
                  v-for="(colName, c) in COLS"
                  :key="colName"
                  class="sea-cell"
                  :class="{
                    'cell-ship': !!getPlacedShipAt(r, c),
                    'cell-preview-valid': isCellInPreview(r, c)?.valid,
                    'cell-preview-invalid': isCellInPreview(r, c) && !isCellInPreview(r, c).valid,
                  }"
                  @mouseenter="hoverPos = { r, c }"
                  @mouseleave="hoverPos = null"
                  @click="onPlaceBoardClick(r, c)"
                >
                  <span v-if="getPlacedShipAt(r, c)" class="ship-icon">⚓</span>
                </div>
              </template>
            </div>
          </div>

          <!-- Danh sách 5 tàu cần đặt -->
          <div class="ship-palette">
            <h4>Hạm đội của bạn</h4>
            <div
              v-for="def in SHIP_DEFS"
              :key="def.name"
              class="ship-card"
              :class="{
                active: selectedShipDef?.name === def.name,
                placed: placedShips.some((s) => s.name === def.name),
              }"
              @click="selectShip(def)"
            >
              <div class="ship-info">
                <strong>{{ def.name }}</strong>
                <span class="small muted">{{ def.len }} ô</span>
              </div>
              <div class="ship-mini-cells">
                <div v-for="i in def.len" :key="i" class="mini-cell"></div>
              </div>
              <button
                v-if="placedShips.some((s) => s.name === def.name)"
                class="btn small"
                @click.stop="removePlacedShip(def.name)"
              >
                Gỡ
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- GIAI ĐOẠN 2 & 3: KHAI HỎA / KẾT THÚC -->
      <div v-else class="battle-container">
        <!-- Vùng biển đối phương (mục tiêu bắn) -->
        <div class="card battle-panel">
          <div class="panel-header">
            <h3>🎯 Vùng biển đối phương (Khai hỏa)</h3>
            <span v-if="canShoot" class="badge-turn you">Lượt bắn của bạn</span>
            <span v-else class="badge-turn wait">Chờ đối thủ…</span>
          </div>

          <div class="sea-board-wrapper">
            <div class="sea-board" :class="{ 'board-disabled': !canShoot }">
              <div class="sea-corner"></div>
              <div v-for="col in COLS" :key="col" class="sea-header-col">{{ col }}</div>

              <template v-for="(rowNum, r) in ROWS" :key="rowNum">
                <div class="sea-header-row">{{ rowNum }}</div>
                <div
                  v-for="(colName, c) in COLS"
                  :key="colName"
                  class="sea-cell clickable"
                  :class="{
                    'cell-hit': getOpponentCellState(r, c)?.isHit,
                    'cell-miss': getOpponentCellState(r, c)?.isMiss,
                    'cell-sunk': getOpponentCellState(r, c)?.isSunk,
                    'cell-revealed': getOpponentCellState(r, c)?.isRevealed,
                    'cell-last-shot': lastShot?.side === you && lastShot?.r === r && lastShot?.c === c,
                  }"
                  @click="onOpponentCellClick(r, c)"
                >
                  <span v-if="getOpponentCellState(r, c)?.isSunk" class="hit-icon">💥</span>
                  <span v-else-if="getOpponentCellState(r, c)?.isHit" class="hit-icon">🔥</span>
                  <span v-else-if="getOpponentCellState(r, c)?.isMiss" class="miss-icon">•</span>
                  <span v-else-if="getOpponentCellState(r, c)?.isRevealed" class="revealed-icon">⚓</span>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- Vùng biển của bạn (radar phòng ngự) -->
        <div class="card battle-panel radar-panel">
          <div class="panel-header">
            <h3>🛡️ Vùng biển của bạn (Phòng thủ)</h3>
            <span class="small muted">Vị trí tàu & các phát bắn từ địch</span>
          </div>

          <div class="sea-board-wrapper small-board">
            <div class="sea-board">
              <div class="sea-corner"></div>
              <div v-for="col in COLS" :key="col" class="sea-header-col">{{ col }}</div>

              <template v-for="(rowNum, r) in ROWS" :key="rowNum">
                <div class="sea-header-row">{{ rowNum }}</div>
                <div
                  v-for="(colName, c) in COLS"
                  :key="colName"
                  class="sea-cell"
                  :class="{
                    'cell-ship': getMyCellState(r, c)?.hasShip,
                    'cell-hit': getMyCellState(r, c)?.isHit,
                    'cell-miss': getMyCellState(r, c)?.isMiss,
                    'cell-sunk': getMyCellState(r, c)?.isSunk,
                    'cell-last-shot': lastShot?.side !== you && lastShot?.r === r && lastShot?.c === c,
                  }"
                >
                  <span v-if="getMyCellState(r, c)?.isSunk" class="hit-icon">💥</span>
                  <span v-else-if="getMyCellState(r, c)?.isHit" class="hit-icon">🔥</span>
                  <span v-else-if="getMyCellState(r, c)?.isMiss" class="miss-icon">•</span>
                  <span v-else-if="getMyCellState(r, c)?.hasShip" class="ship-icon">⚓</span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- CỘT BÊN PHẢI (ASIDE 320px) -->
    <aside class="card side">
      <div class="status" :class="status.tone">{{ status.text }}</div>

      <!-- Thông báo diễn biến -->
      <div v-if="room.notice" class="notice-banner">
        <span>{{ room.notice }}</span>
      </div>

      <!-- Tình trạng hạm đội đối phương -->
      <div class="fleet-status-block">
        <h4>Hạm đội đối thủ</h4>
        <ul class="fleet-list">
          <li
            v-for="ship in opponentShipsList"
            :key="ship.name"
            class="fleet-item"
            :class="{ sunk: ship.sunk }"
          >
            <span class="fleet-name">{{ ship.name }} ({{ ship.len }} ô)</span>
            <span class="fleet-tag">{{ ship.sunk ? 'ĐÃ CHÌM 💥' : 'Hoạt động' }}</span>
          </li>
        </ul>
      </div>

      <!-- Tình trạng hạm đội người chơi -->
      <div class="fleet-status-block">
        <h4>Hạm đội của bạn</h4>
        <ul class="fleet-list">
          <li
            v-for="ship in myShipsList"
            :key="ship.name"
            class="fleet-item"
            :class="{ sunk: ship.sunk }"
          >
            <span class="fleet-name">{{ ship.name }} ({{ ship.len }} ô)</span>
            <span class="fleet-tag">{{ ship.sunk ? 'ĐÃ CHÌM 💥' : 'Hoạt động' }}</span>
          </li>
        </ul>
      </div>

      <!-- Thống kê phát bắn -->
      <dl v-if="phase !== 'placing'" class="meta small">
        <div><dt>Tổng phát bắn</dt><dd><strong>{{ playerStats.shots }}</strong></dd></div>
        <div><dt>Bắn trúng</dt><dd><strong>{{ playerStats.hits }}</strong></dd></div>
        <div><dt>Độ chính xác</dt><dd><strong>{{ playerStats.accuracy }}%</strong></dd></div>
        <div><dt>Độ khó bot</dt><dd>{{ room.levelName || 'Vừa' }}</dd></div>
        <div><dt>Phòng</dt><dd><strong>{{ room.code }}</strong></dd></div>
      </dl>

      <!-- Các nút thao tác -->
      <div class="actions">
        <button class="btn red" :disabled="!you" @click="handleNewGame">
          Ván mới
        </button>
        <button class="btn" @click="handleLeave">
          Rời phòng
        </button>
      </div>

      <p class="small muted">
        Bắn trúng hoặc đánh chìm tàu được bắn tiếp! Bắn trượt sẽ mất lượt.
      </p>
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
  display: grid;
  gap: 16px;
}

.side {
  display: grid;
  gap: 14px;
  position: sticky;
  top: 16px;
}

.status {
  font-size: 1.15rem;
  font-weight: 700;
  text-align: center;
  padding: 6px 0;
}

.status.green { color: var(--green); }
.status.red { color: var(--red); }
.status.blue { color: var(--blue); }
.status.muted { color: var(--muted); }

.notice-banner {
  padding: 8px 12px;
  background: var(--bg);
  border-left: 4px solid var(--accent);
  border-radius: 4px;
  font-size: 0.9rem;
  font-weight: 600;
  text-align: center;
}

/* KHUNG ĐẶT TÀU */
.placing-container {
  display: grid;
  gap: 16px;
}

.placing-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.placing-title h3 {
  margin: 0 0 4px;
}

.placing-title p {
  margin: 0;
}

.placing-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.placing-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 16px;
  align-items: start;
}

.ship-palette {
  display: grid;
  gap: 8px;
}

.ship-palette h4 {
  margin: 0 0 4px;
  font-size: 0.95rem;
  color: var(--muted);
}

.ship-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  cursor: pointer;
  background: var(--bg);
  transition: border-color 0.15s, background-color 0.15s;
}

.ship-card.active {
  border-color: var(--blue);
  box-shadow: 0 0 0 1px var(--blue);
}

.ship-card.placed {
  opacity: 0.65;
  border-style: dashed;
}

.ship-info {
  display: grid;
  gap: 2px;
}

.ship-mini-cells {
  display: flex;
  gap: 3px;
}

.mini-cell {
  width: 10px;
  height: 10px;
  background: var(--blue);
  border-radius: 2px;
}

/* LƯỚI BÀN BIỂN 10x10 */
.sea-board-wrapper {
  width: 100%;
  max-width: 500px;
  margin: 0 auto;
}

.sea-board {
  display: grid;
  grid-template-columns: 26px repeat(10, minmax(0, 1fr));
  gap: 2px;
  background: #1e3a5f;
  padding: 6px;
  border-radius: 10px;
  user-select: none;
}

.sea-corner,
.sea-header-col,
.sea-header-row {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: #8bb4e7;
}

.sea-header-col {
  height: 24px;
}

.sea-header-row {
  width: 24px;
}

.sea-cell {
  aspect-ratio: 1 / 1;
  /* min-size 0 + overflow: emoji 🔥/💥 không được làm giãn ô (lỗi đã gặp ở Dò mìn) */
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  line-height: 1;
  background: #254b77;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: background-color 0.1s, transform 0.05s;
}

.sea-cell.clickable {
  cursor: crosshair;
}

.sea-cell.clickable:hover {
  background: #34679f;
  transform: scale(1.04);
}

.board-disabled .sea-cell.clickable {
  cursor: not-allowed;
}

.board-disabled .sea-cell.clickable:hover {
  background: #254b77;
  transform: none;
}

/* TRẠNG THÁI Ô */
.cell-ship {
  background: #3e6d9c !important;
  border: 1px solid #71a9e1;
}

.ship-icon {
  font-size: 0.95rem;
  color: #fff;
}

.cell-preview-valid {
  background: rgba(56, 126, 87, 0.75) !important;
  border: 1px dashed var(--green);
}

.cell-preview-invalid {
  background: rgba(184, 72, 62, 0.75) !important;
  border: 1px dashed var(--red);
}

.cell-miss {
  background: #193150 !important;
}

.miss-icon {
  font-size: 1.4rem;
  color: #7a94b4;
  line-height: 1;
}

.cell-hit {
  background: #8b2b24 !important;
}

.hit-icon {
  font-size: 1.1rem;
  line-height: 1;
}

.cell-sunk {
  background: #541915 !important;
  box-shadow: inset 0 0 0 1px var(--red);
}

.cell-revealed {
  background: #3e4a59 !important;
  opacity: 0.8;
}

.revealed-icon {
  font-size: 0.9rem;
  color: #b0c4de;
}

.cell-last-shot {
  outline: 2px solid var(--accent);
  outline-offset: -1px;
  animation: pulse-shot 1.5s infinite;
}

@keyframes pulse-shot {
  0% { box-shadow: 0 0 0 0 rgba(238, 182, 61, 0.7); }
  70% { box-shadow: 0 0 0 6px rgba(238, 182, 61, 0); }
  100% { box-shadow: 0 0 0 0 rgba(238, 182, 61, 0); }
}

/* KHUNG CHIẾN ĐẤU (BẮN TÀU) */
.battle-container {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 16px;
}

.battle-panel {
  display: grid;
  gap: 12px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.panel-header h3 {
  margin: 0;
  font-size: 1.05rem;
}

.badge-turn {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 700;
}

.badge-turn.you {
  background: var(--green);
  color: #fff;
}

.badge-turn.wait {
  background: var(--grey);
  color: #fff;
}

.radar-panel {
  opacity: 0.95;
}

.radar-panel .sea-board {
  background: #142841;
}

.radar-panel .sea-cell {
  background: #1b3557;
}

.fleet-status-block {
  display: grid;
  gap: 6px;
}

.fleet-status-block h4 {
  margin: 0;
  font-size: 0.9rem;
  color: var(--muted);
}

.fleet-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}

.fleet-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--bg);
  border: 1px solid var(--panel-border);
  font-size: 0.85rem;
}

.fleet-item.sunk {
  text-decoration: line-through;
  opacity: 0.6;
  border-color: var(--red);
}

.fleet-tag {
  font-size: 0.75rem;
  font-weight: 600;
}

.fleet-item.sunk .fleet-tag {
  color: var(--red);
  text-decoration: none;
}

.meta {
  margin: 0;
  display: grid;
  gap: 4px;
}

.meta div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.meta dt {
  color: var(--muted);
}

.meta dd {
  margin: 0;
  text-align: right;
}

.actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: 8px;
}

@media (max-width: 1050px) {
  .battle-container {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .game {
    grid-template-columns: 1fr;
  }
  .side {
    position: static;
  }
  .placing-body {
    grid-template-columns: 1fr;
  }
}
</style>

