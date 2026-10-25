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
  if (!p || p === '.' || !props.room.you) return false
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

function cornerBracketPath(cx, cy, d = 24, len = 7) {
  return `M ${cx - d} ${cy - d + len} L ${cx - d} ${cy - d} L ${cx - d + len} ${cy - d} ` +
         `M ${cx + d - len} ${cy - d} L ${cx + d} ${cy - d} L ${cx + d} ${cy - d + len} ` +
         `M ${cx - d} ${cy + d - len} L ${cx - d} ${cy + d} L ${cx - d + len} ${cy + d} ` +
         `M ${cx + d - len} ${cy + d} L ${cx + d} ${cy + d} L ${cx + d} ${cy + d - len}`
}

function handleCellClick(r, c) {
  if (!props.canPlay || !props.room.you) return

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
  <div class="wrap">
    <svg class="board" :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" :class="{ playable: canPlay }"
         role="grid" aria-label="Bàn cờ tướng" @click="onSvgClick">
      <defs>
        <filter id="piece-shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="1.5" dy="2.5" stdDeviation="2" flood-color="#000" flood-opacity="0.32" />
        </filter>
        <filter id="selected-piece-shadow" x="-40%" y="-40%" width="180%" height="180%">
          <feDropShadow dx="2" dy="5" stdDeviation="4" flood-color="#000" flood-opacity="0.45" />
        </filter>
      </defs>

      <!-- Nền gỗ bàn cờ -->
      <rect x="0" y="0" :width="WIDTH" :height="HEIGHT" rx="12" class="wood" />

      <!-- Viền khung ngoài -->
      <rect :x="PAD - 6" :y="PAD - 6" :width="8 * CELL + 12" :height="9 * CELL + 12" class="outer-border" />

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

      <!-- Hai cửu cung (đường chéo) -->
      <line :x1="PAD + 3 * CELL" :y1="PAD" :x2="PAD + 5 * CELL" :y2="PAD + 2 * CELL" class="grid-line" />
      <line :x1="PAD + 5 * CELL" :y1="PAD" :x2="PAD + 3 * CELL" :y2="PAD + 2 * CELL" class="grid-line" />
      <line :x1="PAD + 3 * CELL" :y1="PAD + 7 * CELL" :x2="PAD + 5 * CELL" :y2="PAD + 9 * CELL" class="grid-line" />
      <line :x1="PAD + 5 * CELL" :y1="PAD + 7 * CELL" :x2="PAD + 3 * CELL" :y2="PAD + 9 * CELL" class="grid-line" />

      <!-- Chữ trên Sông Sở Hà - Hán Giới -->
      <g class="river-text">
        <text :x="PAD + 2 * CELL" :y="PAD + 4.6 * CELL" text-anchor="middle">
          {{ isFlipped ? 'HÁN GIỚI' : 'SỞ HÀ' }}
        </text>
        <text :x="PAD + 6 * CELL" :y="PAD + 4.6 * CELL" text-anchor="middle">
          {{ isFlipped ? 'SỞ HÀ' : 'HÁN GIỚI' }}
        </text>
      </g>

      <!-- Đánh dấu nước vừa đi (ô đi và ô đến) bằng góc 4 phía và nền nhẹ -->
      <template v-if="room.lastMove">
        <rect :x="toX(room.lastMove[1]) - CELL / 2" :y="toY(room.lastMove[0]) - CELL / 2"
              :width="CELL" :height="CELL" rx="4" class="last-move-bg" />
        <path :d="cornerBracketPath(toX(room.lastMove[1]), toY(room.lastMove[0]))" class="last-move-bracket" />

        <rect :x="toX(room.lastMove[3]) - CELL / 2" :y="toY(room.lastMove[2]) - CELL / 2"
              :width="CELL" :height="CELL" rx="4" class="last-move-bg" />
        <path :d="cornerBracketPath(toX(room.lastMove[3]), toY(room.lastMove[2]))" class="last-move-bracket" />
      </template>

      <!-- Viền sáng xoay quanh quân đang được chọn -->
      <circle v-if="selected"
              :cx="toX(selected.c)" :cy="toY(selected.r)"
              :r="PIECE_R + 5" class="selected-glow" />

      <!-- Vòng tròn đỏ báo hiệu Tướng bị chiếu -->
      <circle v-if="checkedKingPos"
              :cx="toX(checkedKingPos.c)" :cy="toY(checkedKingPos.r)"
              :r="PIECE_R + 5" class="check-ring" />

      <!-- Các quân cờ trên bàn -->
      <g v-for="p in pieces" :key="`p-${p.r}-${p.c}`"
         class="piece-group"
         :class="{
           red: p.red,
           black: !p.red,
           selected: selected && selected.r === p.r && selected.c === p.c,
           mine: isMyPiece(p.char),
         }"
         @click.stop="handleCellClick(p.r, p.c)">
        <!-- Đĩa quân ngoài -->
        <circle :cx="toX(p.c)" :cy="toY(p.r)" :r="PIECE_R" class="piece-outer" />
        <!-- Vòng chỉ trong -->
        <circle :cx="toX(p.c)" :cy="toY(p.r)" :r="PIECE_R - 3.5" class="piece-inner" />
        <!-- Chữ Hán -->
        <text :x="toX(p.c)" :y="toY(p.r)" class="piece-label">
          {{ p.text }}
        </text>
      </g>

      <!-- Các ô đích hợp lệ của quân đang chọn -->
      <g v-for="t in targets" :key="`t-${t.r}-${t.c}`"
         class="target-mark"
         @click.stop="handleCellClick(t.r, t.c)">
        <!-- Ô ăn quân: vòng tròn bao quanh quân đối phương -->
        <circle v-if="t.isCapture"
                :cx="toX(t.c)" :cy="toY(t.r)" :r="PIECE_R + 2.5" class="target-capture-ring" />
        <!-- Ô trống: chấm tròn nhỏ -->
        <circle v-else
                :cx="toX(t.c)" :cy="toY(t.r)" :r="5.5" class="target-dot" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.wrap {
  width: 100%;
  display: grid;
  place-items: center;
}
.board {
  display: block;
  user-select: none;
  width: 100%;
  height: auto;
  max-height: calc(100vh - 110px);
  aspect-ratio: 528 / 584;
  border-radius: var(--radius);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
  margin-inline: auto;
}
.wood {
  fill: var(--board);
}
.outer-border {
  fill: none;
  stroke: var(--board-line);
  stroke-width: 2.5;
}
.grid-line {
  stroke: var(--board-line);
  stroke-width: 1.2;
}
.river-text text {
  font-family: "KaiTi", "STKaiti", "SimSun", "Noto Serif SC", serif;
  font-size: 20px;
  font-weight: 700;
  fill: var(--board-line);
  opacity: 0.65;
  letter-spacing: 6px;
  dominant-baseline: central;
}
.last-move-bg {
  fill: var(--accent);
  opacity: 0.22;
}
.last-move-bracket {
  fill: none;
  stroke: var(--accent);
  stroke-width: 2.5;
}
.selected-glow {
  fill: none;
  stroke: var(--accent);
  stroke-width: 3;
  stroke-dasharray: 6 3;
  animation: rotate-dash 6s linear infinite;
}
@keyframes rotate-dash {
  100% { stroke-dashoffset: 36; }
}
.check-ring {
  fill: none;
  stroke: var(--red);
  stroke-width: 3.5;
  animation: check-pulse 1s infinite alternate ease-in-out;
}
@keyframes check-pulse {
  0% { opacity: 0.35; stroke-width: 2.5; }
  100% { opacity: 1; stroke-width: 4.5; }
}
.piece-group {
  cursor: default;
}
.piece-group.mine,
.playable .piece-group {
  cursor: pointer;
}
.piece-outer {
  fill: #fdf6e7;
  stroke: #d8c8af;
  stroke-width: 1.5;
  filter: url(#piece-shadow);
  transition: stroke 0.15s, stroke-width 0.15s;
}
.piece-inner {
  fill: none;
  stroke-width: 1.2;
}
.piece-label {
  font-family: "KaiTi", "STKaiti", "SimSun", "Noto Serif SC", serif;
  font-size: 24px;
  font-weight: 900;
  text-anchor: middle;
  dominant-baseline: central;
}

/* Đỏ */
.piece-group.red .piece-inner { stroke: #c82323; }
.piece-group.red .piece-label { fill: #c82323; }

/* Đen */
.piece-group.black .piece-inner { stroke: #2b2a27; }
.piece-group.black .piece-label { fill: #2b2a27; }

/* Quân đang chọn */
.piece-group.selected .piece-outer {
  stroke: var(--accent);
  stroke-width: 2.5;
  filter: url(#selected-piece-shadow);
}

/* Điểm đến hợp lệ */
.target-mark {
  cursor: pointer;
}
.target-dot {
  fill: var(--blue);
  opacity: 0.85;
  transition: r 0.15s ease;
}
.target-mark:hover .target-dot {
  r: 8;
  fill: var(--accent);
}
.target-capture-ring {
  fill: rgba(184, 72, 62, 0.2);
  stroke: var(--red);
  stroke-width: 3;
  stroke-dasharray: 6 3;
}
.target-mark:hover .target-capture-ring {
  fill: rgba(184, 72, 62, 0.4);
}
</style>
