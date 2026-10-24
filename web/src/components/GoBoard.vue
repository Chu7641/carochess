<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  room: { type: Object, required: true },
  canPlay: { type: Boolean, default: false },
  ghostSide: { type: Number, default: 1 }, // 1: Đen, 2: Trắng
})
const emit = defineEmits(['play'])

const CELL = 40
const PAD = 36
const MIN_CELL_PX = 28
const MAX_ZOOM = 2

const scroller = ref(null)
const hover = ref(null)
const box = ref({ width: 0, height: 0 })
const zoom = ref(null)
let observer = null

const size = computed(() => props.room.size || props.room.rows || 19)
const width = computed(() => (size.value - 1) * CELL + PAD * 2)
const height = computed(() => (size.value - 1) * CELL + PAD * 2)
const at = (n) => PAD + n * CELL

// Ký hiệu cột chuẩn cờ vây: bỏ chữ "I" để tránh nhầm với số "1"
const COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T']

const fitScale = computed(() => {
  if (!box.value.width) return 1
  return Math.min(box.value.width / width.value, box.value.height / height.value)
})
const minScale = computed(() => Math.min(fitScale.value, 1))
const scale = computed(() => zoom.value ?? Math.max(fitScale.value, MIN_CELL_PX / CELL))
const cellPx = computed(() => Math.round(CELL * scale.value))
const overflows = computed(() =>
  width.value * scale.value > box.value.width + 1 || height.value * scale.value > box.value.height + 1)

const stones = computed(() => {
  const list = []
  if (!props.room.board) return list
  props.room.board.forEach((row, r) => row.forEach((side, c) => {
    if (side) list.push({ r, c, side })
  }))
  return list
})

const stars = computed(() => {
  const s = size.value
  if (s === 19) {
    return [
      [3, 3], [3, 9], [3, 15],
      [9, 3], [9, 9], [9, 15],
      [15, 3], [15, 9], [15, 15],
    ]
  }
  if (s === 13) {
    return [
      [3, 3], [3, 9],
      [6, 6],
      [9, 3], [9, 9],
    ]
  }
  if (s === 9) {
    return [
      [2, 2], [2, 6],
      [4, 4],
      [6, 2], [6, 6],
    ]
  }
  return []
})

function cellAt(event) {
  const svg = event.currentTarget.ownerSVGElement
  if (!svg) return null
  const rect = svg.getBoundingClientRect()
  const x = (event.clientX - rect.left) * (width.value / rect.width)
  const y = (event.clientY - rect.top) * (height.value / rect.height)
  const c = Math.round((x - PAD) / CELL)
  const r = Math.round((y - PAD) / CELL)
  return r >= 0 && c >= 0 && r < size.value && c < size.value ? [r, c] : null
}

function onMove(event) {
  const cell = cellAt(event)
  if (cell?.[0] !== hover.value?.[0] || cell?.[1] !== hover.value?.[1]) {
    hover.value = cell
  }
}

function onClick(event) {
  const cell = cellAt(event)
  if (cell && props.canPlay && props.room.board && !props.room.board[cell[0]][cell[1]]) {
    emit('play', cell[0], cell[1])
  }
}

function reveal(r, c, center = false, smooth = true) {
  const el = scroller.value
  if (!el || !overflows.value) return
  const x = at(c) * scale.value
  const y = at(r) * scale.value
  const margin = cellPx.value * 3
  const visible = x > el.scrollLeft + margin && x < el.scrollLeft + el.clientWidth - margin
    && y > el.scrollTop + margin && y < el.scrollTop + el.clientHeight - margin
  if (center || !visible) {
    el.scrollTo({
      left: x - el.clientWidth / 2,
      top: y - el.clientHeight / 2,
      behavior: smooth ? 'smooth' : 'auto',
    })
  }
}

function focusPoint() {
  const last = props.room.lastMove
  return last ?? [Math.floor(size.value / 2), Math.floor(size.value / 2)]
}

async function setZoom(next) {
  const el = scroller.value
  const cx = el ? (el.scrollLeft + el.clientWidth / 2) / scale.value : 0
  const cy = el ? (el.scrollTop + el.clientHeight / 2) / scale.value : 0
  zoom.value = next == null ? null : Math.min(MAX_ZOOM, Math.max(minScale.value, next))
  await nextTick()
  if (el) el.scrollTo(cx * scale.value - el.clientWidth / 2, cy * scale.value - el.clientHeight / 2)
}

const zoomIn = () => setZoom(scale.value * 1.25)
const zoomOut = () => setZoom(scale.value / 1.25)
const zoomFit = () => setZoom(minScale.value)

watch(() => props.room.lastMove, (last) => { if (last) reveal(last[0], last[1]) })
watch(() => `${props.room.code}:${size.value}`, async () => {
  zoom.value = null
  await nextTick()
  reveal(...focusPoint(), true, false)
})

onMounted(() => {
  observer = new ResizeObserver(([entry]) => {
    const first = !box.value.width
    box.value = { width: entry.contentRect.width, height: entry.contentRect.height }
    if (first) nextTick(() => reveal(...focusPoint(), true, false))
  })
  if (scroller.value) observer.observe(scroller.value)
})
onUnmounted(() => observer?.disconnect())
</script>

<template>
  <div class="wrap">
    <div ref="scroller" class="scroller" :class="{ overflows }">
      <svg class="board" :viewBox="`0 0 ${width} ${height}`" :class="{ playable: canPlay }"
           :width="width * scale" :height="height * scale"
           role="grid" aria-label="Bàn cờ vây">
        <defs>
          <radialGradient id="go-black" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stop-color="#555" />
            <stop offset="40%" stop-color="#282828" />
            <stop offset="100%" stop-color="#111" />
          </radialGradient>
          <radialGradient id="go-white" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stop-color="#ffffff" />
            <stop offset="60%" stop-color="#f0f0f0" />
            <stop offset="100%" stop-color="#d4d4d4" />
          </radialGradient>
          <filter id="stone-shadow" x="-20%" y="-20%" width="150%" height="150%">
            <feDropShadow dx="1.5" dy="2.5" stdDeviation="2" flood-color="#000" flood-opacity="0.35" />
          </filter>
        </defs>

        <!-- Mặt gỗ bàn cờ -->
        <rect x="4" y="4" :width="width - 8" :height="height - 8" rx="10" class="wood" />

        <!-- Tọa độ mép bàn -->
        <g class="coords">
          <text v-for="c in size" :key="`c-top-${c}`" :x="at(c - 1)" :y="PAD * 0.45">
            {{ COLS[c - 1] }}
          </text>
          <text v-for="c in size" :key="`c-bot-${c}`" :x="at(c - 1)" :y="height - PAD * 0.35">
            {{ COLS[c - 1] }}
          </text>
          <text v-for="r in size" :key="`r-left-${r}`" :x="PAD * 0.4" :y="at(r - 1)">
            {{ size - r + 1 }}
          </text>
          <text v-for="r in size" :key="`r-right-${r}`" :x="width - PAD * 0.4" :y="at(r - 1)">
            {{ size - r + 1 }}
          </text>
        </g>

        <!-- Lưới bàn cờ -->
        <g class="grid">
          <line v-for="r in size" :key="`r${r}`" :x1="at(0)" :x2="at(size - 1)"
                :y1="at(r - 1)" :y2="at(r - 1)" />
          <line v-for="c in size" :key="`c${c}`" :y1="at(0)" :y2="at(size - 1)"
                :x1="at(c - 1)" :x2="at(c - 1)" />
        </g>

        <!-- Các điểm sao (hoshi) -->
        <circle v-for="[r, c] in stars" :key="`s${r}-${c}`" :cx="at(c)" :cy="at(r)" r="3.5" class="star" />

        <!-- Quân cờ -->
        <g v-for="s in stones" :key="`p${s.r}-${s.c}`" class="stone" :class="s.side === 1 ? 'black' : 'white'">
          <circle :cx="at(s.c)" :cy="at(s.r)" :r="CELL * 0.46" filter="url(#stone-shadow)" />
        </g>

        <!-- Điểm đánh dấu nước đi gần nhất -->
        <circle v-if="room.lastMove" :cx="at(room.lastMove[1])" :cy="at(room.lastMove[0])"
                :r="CELL * 0.14" class="last-dot"
                :class="room.board && room.board[room.lastMove[0]][room.lastMove[1]] === 1 ? 'on-black' : 'on-white'" />

        <!-- Quân bóng mờ khi rê chuột -->
        <circle v-if="canPlay && hover && room.board && !room.board[hover[0]][hover[1]]"
                :cx="at(hover[1])" :cy="at(hover[0])" :r="CELL * 0.46"
                class="ghost" :class="ghostSide === 1 ? 'ghost-black' : 'ghost-white'" />

        <!-- Vùng bắt sự kiện chuột -->
        <rect class="hit" x="0" y="0" :width="width" :height="height"
              @mousemove="onMove" @mouseleave="hover = null" @click="onClick" />
      </svg>
    </div>

    <!-- Nút điều khiển phóng to thu nhỏ -->
    <div class="zoom" role="group" aria-label="Phóng to thu nhỏ">
      <button class="zbtn" title="Thu nhỏ" :disabled="scale <= minScale + 0.001" @click="zoomOut">−</button>
      <button class="zbtn wide" title="Xem trọn bàn cờ" @click="zoomFit">Toàn bàn</button>
      <button class="zbtn" title="Phóng to" :disabled="scale >= MAX_ZOOM - 0.001" @click="zoomIn">+</button>
      <button class="zbtn wide" title="Về nước vừa đánh" :disabled="!overflows"
              @click="reveal(...focusPoint(), true)">Nước mới</button>
    </div>
  </div>
</template>

<style scoped>
.wrap { position: relative; width: 100%; }
.scroller {
  width: 100%;
  height: calc(100vh - 110px);
  min-height: 320px;
  overflow: auto;
  display: flex;
  border-radius: 12px;
  overscroll-behavior: contain;
}
.board { display: block; user-select: none; flex: none; margin: auto; }
.wood { fill: #dcb36c; }
.coords text {
  fill: #614620;
  font: 600 11px Arial, sans-serif;
  text-anchor: middle;
  dominant-baseline: central;
}
.grid line { stroke: #523c1e; stroke-width: 1.1; }
.star { fill: #483418; }
.stone.black circle { fill: url(#go-black); }
.stone.white circle { fill: url(#go-white); stroke: #bbb; stroke-width: 0.6; }
.last-dot.on-black { fill: #fff; opacity: 0.9; }
.last-dot.on-white { fill: #111; opacity: 0.85; }
.ghost { pointer-events: none; opacity: 0.45; }
.ghost-black { fill: #111; }
.ghost-white { fill: #fff; stroke: #999; }
.hit { fill: transparent; }
.playable .hit { cursor: pointer; }

.zoom {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 10px;
  background: rgb(52 47 40 / 0.85);
  box-shadow: 0 4px 14px rgb(0 0 0 / 0.25);
}
.zbtn {
  min-width: 34px;
  height: 32px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #fff5de;
  font-weight: 700;
  font-size: 1rem;
  cursor: pointer;
}
.zbtn.wide { font-size: 0.8rem; padding: 0 8px; }
.zbtn:hover:not(:disabled) { background: rgb(255 255 255 / 0.14); }
.zbtn:disabled { opacity: 0.4; cursor: default; }
@media (max-width: 860px) {
  .scroller { height: min(100vw, calc(100vh - 140px)); }
}
</style>
