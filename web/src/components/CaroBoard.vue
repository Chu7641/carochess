<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { X } from '../game.js'

const props = defineProps({
  room: { type: Object, required: true },
  canPlay: { type: Boolean, default: false },
  ghostSide: { type: Number, default: X },
})
const emit = defineEmits(['play'])

const CELL = 40          // đơn vị trong viewBox
const PAD = 30
const MIN_CELL_PX = 28   // nhỏ hơn thì khó bấm: chuyển sang cuộn bàn cờ
const MAX_ZOOM = 2

const scroller = ref(null)
const hover = ref(null)
const box = ref({ width: 0, height: 0 })
const zoom = ref(null)   // null: tự động (vừa khung, nhưng không nhỏ hơn MIN_CELL_PX)
let observer = null

const width = computed(() => (props.room.cols - 1) * CELL + PAD * 2)
const height = computed(() => (props.room.rows - 1) * CELL + PAD * 2)
const at = (n) => PAD + n * CELL

// Tỉ lệ để thấy trọn bàn cờ trong khung hiện tại.
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
  props.room.board.forEach((row, r) => row.forEach((side, c) => {
    if (side) list.push({ r, c, side })
  }))
  return list
})

const stars = computed(() => {
  const cr = Math.floor(props.room.rows / 2)
  const cc = Math.floor(props.room.cols / 2)
  return [[0, 0], [-4, -4], [-4, 4], [4, -4], [4, 4]]
    .map(([dr, dc]) => [cr + dr, cc + dc])
    .filter(([r, c]) => r >= 0 && c >= 0 && r < props.room.rows && c < props.room.cols)
})

const winLine = computed(() => {
  const line = props.room.winLine
  return line && line.length ? [line[0], line[line.length - 1]] : null
})

// Một lớp nhận chuột duy nhất thay cho hàng nghìn ô: đổi tọa độ chuột sang ô cờ.
function cellAt(event) {
  const rect = event.currentTarget.ownerSVGElement.getBoundingClientRect()
  const x = (event.clientX - rect.left) * (width.value / rect.width)
  const y = (event.clientY - rect.top) * (height.value / rect.height)
  const c = Math.round((x - PAD) / CELL)
  const r = Math.round((y - PAD) / CELL)
  return r >= 0 && c >= 0 && r < props.room.rows && c < props.room.cols ? [r, c] : null
}

function onMove(event) {
  const cell = cellAt(event)
  if (cell?.[0] !== hover.value?.[0] || cell?.[1] !== hover.value?.[1]) hover.value = cell
}

function onClick(event) {
  const cell = cellAt(event)
  if (cell && props.canPlay && !props.room.board[cell[0]][cell[1]]) emit('play', cell[0], cell[1])
}

// Giữ ô (r, c) trong tầm nhìn; center = true thì đưa ô đó vào giữa khung.
function reveal(r, c, center = false, smooth = true) {
  const el = scroller.value
  if (!el || !overflows.value) return
  const x = at(c) * scale.value
  const y = at(r) * scale.value
  const margin = cellPx.value * 3
  const visible = x > el.scrollLeft + margin && x < el.scrollLeft + el.clientWidth - margin
    && y > el.scrollTop + margin && y < el.scrollTop + el.clientHeight - margin
  if (center || !visible) {
    el.scrollTo({ left: x - el.clientWidth / 2, top: y - el.clientHeight / 2,
                  behavior: smooth ? 'smooth' : 'auto' })
  }
}

function focusPoint() {
  const last = props.room.lastMove
  return last ?? [Math.floor(props.room.rows / 2), Math.floor(props.room.cols / 2)]
}

async function setZoom(next) {
  const el = scroller.value
  // Giữ nguyên điểm đang ở giữa khung khi phóng to/thu nhỏ.
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
watch(() => `${props.room.code}:${props.room.rows}x${props.room.cols}`, async () => {
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
  observer.observe(scroller.value)
})
onUnmounted(() => observer?.disconnect())
</script>

<template>
  <div class="wrap">
    <div ref="scroller" class="scroller" :class="{ overflows }">
      <svg class="board" :viewBox="`0 0 ${width} ${height}`" :class="{ playable: canPlay }"
           :width="width * scale" :height="height * scale"
           role="grid" aria-label="Bàn cờ caro">
        <rect x="4" y="4" :width="width - 8" :height="height - 8" rx="10" class="wood" />
        <g class="grid">
          <line v-for="r in room.rows" :key="`r${r}`" :x1="at(0)" :x2="at(room.cols - 1)"
                :y1="at(r - 1)" :y2="at(r - 1)" />
          <line v-for="c in room.cols" :key="`c${c}`" :y1="at(0)" :y2="at(room.rows - 1)"
                :x1="at(c - 1)" :x2="at(c - 1)" />
        </g>
        <circle v-for="[r, c] in stars" :key="`s${r}-${c}`" :cx="at(c)" :cy="at(r)" r="3.5" class="star" />

        <g v-for="s in stones" :key="`p${s.r}-${s.c}`" class="stone" :class="s.side === X ? 'x' : 'o'">
          <circle :cx="at(s.c)" :cy="at(s.r)" :r="CELL * 0.4" />
          <text :x="at(s.c)" :y="at(s.r)">{{ s.side === X ? 'X' : 'O' }}</text>
        </g>
        <circle v-if="room.lastMove" :cx="at(room.lastMove[1])" :cy="at(room.lastMove[0])"
                :r="CELL * 0.47" class="last" />
        <line v-if="winLine" class="win" :x1="at(winLine[0][1])" :y1="at(winLine[0][0])"
              :x2="at(winLine[1][1])" :y2="at(winLine[1][0])" />

        <circle v-if="canPlay && hover && !room.board[hover[0]][hover[1]]"
                :cx="at(hover[1])" :cy="at(hover[0])" :r="CELL * 0.4"
                class="ghost" :class="ghostSide === X ? 'x' : 'o'" />
        <rect class="hit" x="0" y="0" :width="width" :height="height"
              @mousemove="onMove" @mouseleave="hover = null" @click="onClick" />
      </svg>
    </div>

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
/* margin: auto canh giữa khi bàn nhỏ hơn khung, nhưng không cắt mép khi bàn lớn hơn. */
.board { display: block; user-select: none; flex: none; margin: auto; }
.wood { fill: var(--board); }
.grid line { stroke: var(--board-line); stroke-width: 1.2; }
.star { fill: var(--board-line); }
.stone circle { stroke: #fff7e6; stroke-width: 1.5; }
.stone.x circle { fill: var(--stone-x); }
.stone.o circle { fill: var(--stone-o); }
.stone text {
  fill: #fff;
  font: 700 18px Arial, sans-serif;
  text-anchor: middle;
  dominant-baseline: central;
  pointer-events: none;
}
.last { fill: none; stroke: #2fae62; stroke-width: 3; pointer-events: none; }
.win { stroke: #ff393d; stroke-width: 6; stroke-linecap: round; opacity: 0.9; pointer-events: none; }
.ghost { opacity: 0.35; pointer-events: none; }
.ghost.x { fill: var(--stone-x); }
.ghost.o { fill: var(--stone-o); }
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
