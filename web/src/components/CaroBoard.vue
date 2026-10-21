<script setup>
import { computed, ref } from 'vue'
import { X } from '../game.js'

const props = defineProps({
  room: { type: Object, required: true },
  canPlay: { type: Boolean, default: false },
  ghostSide: { type: Number, default: X },
})
const emit = defineEmits(['play'])

const CELL = 40
const PAD = 30
const hover = ref(null)

const width = computed(() => (props.room.cols - 1) * CELL + PAD * 2)
const height = computed(() => (props.room.rows - 1) * CELL + PAD * 2)
const at = (n) => PAD + n * CELL

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

const cells = computed(() => {
  const list = []
  for (let r = 0; r < props.room.rows; r++) {
    for (let c = 0; c < props.room.cols; c++) list.push([r, c])
  }
  return list
})

const winLine = computed(() => {
  const line = props.room.winLine
  return line && line.length ? [line[0], line[line.length - 1]] : null
})

function play(r, c) {
  if (props.canPlay && !props.room.board[r][c]) emit('play', r, c)
}
</script>

<template>
  <svg class="board" :viewBox="`0 0 ${width} ${height}`" :class="{ playable: canPlay }"
       role="grid" aria-label="Bàn cờ caro" @mouseleave="hover = null">
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
    <rect v-for="[r, c] in cells" :key="`h${r}-${c}`" class="hit"
          :x="at(c) - CELL / 2" :y="at(r) - CELL / 2" :width="CELL" :height="CELL"
          @mouseenter="hover = [r, c]" @click="play(r, c)" />
  </svg>
</template>

<style scoped>
.board { width: 100%; height: auto; max-height: calc(100vh - 120px); display: block; user-select: none; }
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
.last { fill: none; stroke: #2fae62; stroke-width: 3; }
.win { stroke: #ff393d; stroke-width: 6; stroke-linecap: round; opacity: 0.9; }
.ghost { opacity: 0.35; pointer-events: none; }
.ghost.x { fill: var(--stone-x); }
.ghost.o { fill: var(--stone-o); }
.hit { fill: transparent; }
.playable .hit { cursor: pointer; }
</style>
