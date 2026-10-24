<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  room: { type: Object, required: true },
  canPlay: { type: Boolean, default: false },
})
const emit = defineEmits(['movePiece'])

const CELL = 56
const PAD = 40
const WIDTH = 8 * CELL + PAD * 2   // 528
const HEIGHT = 9 * CELL + PAD * 2  // 584
const PIECE_R = 24

const selected = ref(null) // { r, c }

const isFlipped = computed(() => props.room.you === 2) // Cầm Đen thì lật bàn 180 độ

function toX(c) {
  const col = isFlipped.value ? 8 - c : c
  return PAD + col * CELL
}

function toY(r) {
  const row = isFlipped.value ? 9 - r : r
  return PAD + row * CELL
}

function fromXY(x, y) {
  const c = Math.round((x - PAD) / CELL)
  const r = Math.round((y - PAD) / CELL)
  if (r < 0 || r > 9 || c < 0 || c > 8) return null
  return {
    r: isFlipped.value ? 9 - r : r,
    c: isFlipped.value ? 8 - c : c,
  }
}

const PIECE_TEXT = {
  K: '帥', A: '仕', B: '相', N: '傌', R: '俥', C: '炮', P: '兵',
  k: '將', a: '士', b: '象', n: '馬', r: '車', c: '砲', p: '卒',
}

const isRedPiece = (p) => p && p !== '.' && p === p.toUpperCase()
const isBlackPiece = (p) => p && p !== '.' && p === p.toLowerCase()
const isMyPiece = (p) => {
  if (!p || p === '.') return false
  return props.room.you === 1 ? isRedPiece(p) : isBlackPiece(p)
}

const pieces = computed(() => {
  const list = []
  if (!props.room.board) return list
  for (let r = 0; r < 10; r++) {
    for (let c = 0; c < 9; c++) {
      const p = props.room.board[r]?.[c]
      if (p && p !== '.') {
        list.push({ r, c, char: p, text: PIECE_TEXT[p] || p, red: isRedPiece(p) })
      }
    }
  }
  return list
})

// Các nước đi hợp lệ từ ô đang chọn
const targets = computed(() => {
  if (!selected.value || !props.room.legalMoves) return []
  const { r, c } = selected.value
  const res = []
  for (const m of props.room.legalMoves) {
    if (m[0] === r && m[1] === c) {
      const tr = m[2]
      const tc = m[3]
      const destPiece = props.room.board?.[tr]?.[tc]
      res.push({
        r: tr,
        c: tc,
        isCapture: destPiece && destPiece !== '.',
      })
    }
  }
  return res
})

// Vị trí Tướng bị chiếu
const checkedKingPos = computed(() => {
  if (!props.room.inCheck || !props.room.board) return null
  const current = props.room.current
  const kingChar = current === 1 ? 'K' : 'k'
  for (let r = 0; r < 10; r++) {
    for (let c = 0; c < 9; c++) {
      if (props.room.board[r]?.[c] === kingChar) {
        return { r, c }
      }
    }
  }
  return null
})

function handleCellClick(r, c) {
  if (!props.canPlay) return

  const p = props.room.board?.[r]?.[c]

  // Nếu đang chọn một quân và bấm vào một ô đích hợp lệ
  if (selected.value) {
    const isTarget = targets.value.some((t) => t.r === r && t.c === c)
    if (isTarget) {
      emit('movePiece', selected.value.r, selected.value.c, r, c)
      selected.value = null
      return
    }
  }

  // Nếu bấm vào quân của mình: chọn hoặc đổi chọn
  if (isMyPiece(p)) {
    selected.value = { r, c }
  } else {
    // Bấm ra ngoài hoặc quân đối phương không phải ô đích -> bỏ chọn
    selected.value = null
  }
}

function onSvgClick(event) {
  const svg = event.currentTarget
  const rect = svg.getBoundingClientRect()
  const clickX = (event.clientX - rect.left) * (WIDTH / rect.width)
  const clickY = (event.clientY - rect.top) * (HEIGHT / rect.height)
  const cell = fromXY(clickX, clickY)
  if (cell) {
    handleCellClick(cell.r, cell.c)
  } else {
    selected.value = null
  }
}
</script>

<template>
  <div class="board-container">
    <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" class="xiangqi-svg" @click="onSvgClick">
      <!-- Nền bàn cờ màu gỗ ấm -->
      <rect x="10" y="10" :width="WIDTH - 20" :height="HEIGHT - 20" rx="8" class="board-bg" />
      <rect :x="PAD - 6" :y="PAD - 6" :width="8 * CELL + 12" :height="9 * CELL + 12" class="board-border" />

      <!-- Các đường ngang (10 hàng) -->
      <line v-for="r in 10" :key="`h-${r}`"
            :x1="PAD" :y1="PAD + (r - 1) * CELL"
            :x2="PAD + 8 * CELL" :y2="PAD + (r - 1) * CELL"
            class="grid-line" />

      <!-- Các đường dọc (9 cột): 2 cột biên liên tục, 7 cột giữa đứt ở sông -->
      <line :x1="PAD" :y1="PAD" :x2="PAD" :y2="PAD + 9 * CELL" class="grid-line" />
      <line :x1="PAD + 8 * CELL" :y1="PAD" :x2="PAD + 8 * CELL" :y2="PAD + 9 * CELL" class="grid-line" />

      <template v-for="c in 7" :key="`v-${c}`">
        <line :x1="PAD + c * CELL" :y1="PAD"
              :x2="PAD + c * CELL" :y2="PAD + 4 * CELL"
              class="grid-line" />
        <line :x1="PAD + c * CELL" :y1="PAD + 5 * CELL"
              :x2="PAD + c * CELL" :y2="PAD + 9 * CELL"
              class="grid-line" />
      </template>

      <!-- Hai cung cửu cung (đường chéo) -->
      <!-- Cung trên -->
      <line :x1="PAD + 3 * CELL" :y1="PAD" :x2="PAD + 5 * CELL" :y2="PAD + 2 * CELL" class="grid-line" />
      <line :x1="PAD + 5 * CELL" :y1="PAD" :x2="PAD + 3 * CELL" :y2="PAD + 2 * CELL" class="grid-line" />
      <!-- Cung dưới -->
      <line :x1="PAD + 3 * CELL" :y1="PAD + 7 * CELL" :x2="PAD + 5 * CELL" :y2="PAD + 9 * CELL" class="grid-line" />
      <line :x1="PAD + 5 * CELL" :y1="PAD + 7 * CELL" :x2="PAD + 3 * CELL" :y2="PAD + 9 * CELL" class="grid-line" />

      <!-- Chữ trên Sông Sở Hà - Hán Giới -->
      <g class="river-text">
        <text :x="PAD + 2 * CELL" :y="PAD + 4.65 * CELL" text-anchor="middle">
          {{ isFlipped ? 'HÁN GIỚI' : 'SỞ HÀ' }}
        </text>
        <text :x="PAD + 6 * CELL" :y="PAD + 4.65 * CELL" text-anchor="middle">
          {{ isFlipped ? 'SỞ HÀ' : 'HÁN GIỚI' }}
        </text>
      </g>

      <!-- Đánh dấu nước vừa đi (ô đi và ô đến) -->
      <template v-if="room.lastMove">
        <rect :x="toX(room.lastMove[1]) - CELL / 2" :y="toY(room.lastMove[0]) - CELL / 2"
              :width="CELL" :height="CELL" class="last-move-marker" />
        <rect :x="toX(room.lastMove[3]) - CELL / 2" :y="toY(room.lastMove[2]) - CELL / 2"
              :width="CELL" :height="CELL" class="last-move-marker" />
      </template>

      <!-- Tô sáng quân đang được chọn -->
      <circle v-if="selected"
              :cx="toX(selected.c)" :cy="toY(selected.r)"
              :r="PIECE_R + 3" class="selected-glow" />

      <!-- Vòng tròn đỏ báo hiệu Tướng bị chiếu -->
      <circle v-if="checkedKingPos"
              :cx="toX(checkedKingPos.c)" :cy="toY(checkedKingPos.r)"
              :r="PIECE_R + 4" class="check-ring" />

      <!-- Các quân cờ trên bàn -->
      <g v-for="p in pieces" :key="`p-${p.r}-${p.c}`"
         class="piece-group"
         :class="{ red: p.red, black: !p.red, mine: isMyPiece(p.char) }"
         @click.stop="handleCellClick(p.r, p.c)">
        <!-- Đĩa quân -->
        <circle :cx="toX(p.c)" :cy="toY(p.r)" :r="PIECE_R" class="piece-body" />
        <circle :cx="toX(p.c)" :cy="toY(p.r)" :r="PIECE_R - 3" class="piece-inner-ring" />
        <!-- Chữ Hán -->
        <text :x="toX(p.c)" :y="toY(p.r) + 7" text-anchor="middle" class="piece-label">
          {{ p.text }}
        </text>
      </g>

      <!-- Các ô đích hợp lệ của quân đang chọn -->
      <g v-for="t in targets" :key="`t-${t.r}-${t.c}`"
         class="target-mark"
         @click.stop="handleCellClick(t.r, t.c)">
        <!-- Ô ăn quân: vòng tròn bao quanh quân đối phương -->
        <circle v-if="t.isCapture"
                :cx="toX(t.c)" :cy="toY(t.r)" :r="PIECE_R + 2" class="target-capture-ring" />
        <!-- Ô trống: chấm tròn nhỏ -->
        <circle v-else
                :cx="toX(t.c)" :cy="toY(t.r)" :r="6" class="target-dot" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.board-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  max-width: 540px;
  margin: 0 auto;
}
.xiangqi-svg {
  width: 100%;
  height: auto;
  max-height: 82vh;
  user-select: none;
  filter: drop-shadow(0 4px 14px rgba(0, 0, 0, 0.25));
}
.board-bg {
  fill: #eacb97;
  stroke: #8d5d2a;
  stroke-width: 3;
}
.board-border {
  fill: none;
  stroke: #5c3514;
  stroke-width: 2.5;
}
.grid-line {
  stroke: #6a3e18;
  stroke-width: 1.5;
}
.river-text text {
  font-family: "KaiTi", "Baskerville", "STKaiti", "SimSun", "Noto Serif SC", serif;
  font-size: 20px;
  font-weight: 700;
  fill: #7d491f;
  letter-spacing: 6px;
}
.last-move-marker {
  fill: rgba(230, 160, 20, 0.35);
  stroke: #d97706;
  stroke-width: 2;
  rx: 4;
}
.selected-glow {
  fill: none;
  stroke: #2563eb;
  stroke-width: 4;
  stroke-dasharray: 4 2;
  animation: rotate 6s linear infinite;
}
@keyframes rotate {
  100% { stroke-dashoffset: 40; }
}
.check-ring {
  fill: none;
  stroke: #dc2626;
  stroke-width: 4;
  animation: pulse 1s infinite alternate ease-in-out;
}
@keyframes pulse {
  0% { transform: scale(0.96); opacity: 0.8; }
  100% { transform: scale(1.04); opacity: 1; }
}
.piece-group {
  cursor: pointer;
  transition: transform 0.1s ease;
}
.piece-group:hover .piece-body {
  filter: brightness(1.06);
}
.piece-body {
  fill: #fff5e0;
  stroke: #73451c;
  stroke-width: 2;
}
.piece-inner-ring {
  fill: none;
  stroke-width: 1.2;
}
.piece-label {
  font-family: "KaiTi", "STKaiti", "SimSun", "Noto Serif SC", serif;
  font-size: 25px;
  font-weight: 900;
}

/* Đỏ */
.piece-group.red .piece-inner-ring { stroke: #c82323; }
.piece-group.red .piece-label { fill: #c82323; }

/* Đen */
.piece-group.black .piece-inner-ring { stroke: #1e293b; }
.piece-group.black .piece-label { fill: #1e293b; }

/* Điểm đích */
.target-mark {
  cursor: pointer;
}
.target-dot {
  fill: #2563eb;
  opacity: 0.85;
  transition: r 0.15s;
}
.target-mark:hover .target-dot {
  r: 9;
  fill: #1d4ed8;
}
.target-capture-ring {
  fill: rgba(220, 38, 38, 0.25);
  stroke: #dc2626;
  stroke-width: 3.5;
  stroke-dasharray: 6 3;
}
.target-mark:hover .target-capture-ring {
  fill: rgba(220, 38, 38, 0.45);
}
</style>

