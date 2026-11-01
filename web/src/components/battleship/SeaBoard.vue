<script setup>
import BattleshipShip from '../BattleshipShip.vue'

const COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
const ROWS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

defineProps({
  disabled: { type: Boolean, default: false },
  ships: { type: Array, default: () => [] },
  getCellState: { type: Function, default: () => ({}) },
})

defineEmits(['cell-click', 'cell-enter', 'cell-leave'])
</script>

<template>
  <div class="sea-board-wrapper">
    <div class="sea-board" :class="{ 'board-disabled': disabled }">
      <!-- Góc trống A1 -->
      <div class="sea-corner"></div>

      <!-- Tiêu đề cột A-J -->
      <div v-for="(col, c) in COLS" :key="col" class="sea-header-col" :class="`c-${c}`">
        {{ col }}
      </div>

      <!-- 10 Hàng ô -->
      <template v-for="(rowNum, r) in ROWS" :key="rowNum">
        <div class="sea-header-row" :class="`r-${r}`">{{ rowNum }}</div>
        <div
          v-for="(colName, c) in COLS"
          :key="colName"
          class="sea-cell"
          :class="[
            `r-${r}`,
            `c-${c}`,
            {
              clickable: getCellState(r, c).clickable,
              'cell-over-ship': getCellState(r, c).overShip,
              'cell-hit': getCellState(r, c).isHit,
              'cell-miss': getCellState(r, c).isMiss,
              'cell-last-shot': getCellState(r, c).isLastShot,
            }
          ]"
          @click="$emit('cell-click', r, c)"
          @mouseenter="$emit('cell-enter', r, c)"
          @mouseleave="$emit('cell-leave', r, c)"
        >
          <span v-if="getCellState(r, c).isSunk" class="hit-icon">💥</span>
          <span v-else-if="getCellState(r, c).isHit" class="hit-icon">🔥</span>
          <span v-else-if="getCellState(r, c).isMiss" class="miss-icon">•</span>
        </div>
      </template>

      <!-- Các tàu trên bàn -->
      <div
        v-for="ship in ships"
        :key="ship.key || ship.name"
        class="sea-ship"
        :class="{
          'sea-ship-preview': ship.preview,
          'sea-ship-revealed': ship.revealed,
        }"
        :style="{
          gridColumn: `${ship.c + 2} / span ${ship.vertical ? 1 : ship.len}`,
          gridRow: `${ship.r + 2} / span ${ship.vertical ? ship.len : 1}`
        }"
      >
        <BattleshipShip
          :name="ship.name"
          :len="ship.len"
          :vertical="ship.vertical"
          :state="ship.state || (ship.sunk ? 'sunk' : (ship.preview ? (ship.previewBad ? 'preview-bad' : 'preview-ok') : 'normal'))"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.sea-board-wrapper {
  width: 100%;
  max-width: 500px;
  margin: 0 auto;
}

.sea-board {
  position: relative;
  isolation: isolate;
  display: grid;
  grid-template-columns: 26px repeat(10, minmax(0, 1fr));
  grid-template-rows: 24px repeat(10, minmax(0, 1fr));
  gap: 2px;
  background: #1e3a5f;
  padding: 6px;
  border-radius: 10px;
  user-select: none;
}

.r-0 { grid-row: 2; }
.r-1 { grid-row: 3; }
.r-2 { grid-row: 4; }
.r-3 { grid-row: 5; }
.r-4 { grid-row: 6; }
.r-5 { grid-row: 7; }
.r-6 { grid-row: 8; }
.r-7 { grid-row: 9; }
.r-8 { grid-row: 10; }
.r-9 { grid-row: 11; }

.c-0 { grid-column: 2; }
.c-1 { grid-column: 3; }
.c-2 { grid-column: 4; }
.c-3 { grid-column: 5; }
.c-4 { grid-column: 6; }
.c-5 { grid-column: 7; }
.c-6 { grid-column: 8; }
.c-7 { grid-column: 9; }
.c-8 { grid-column: 10; }
.c-9 { grid-column: 11; }

.sea-corner {
  grid-row: 1;
  grid-column: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sea-header-col {
  grid-row: 1;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: #8bb4e7;
}

.sea-header-row {
  grid-column: 1;
  width: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: #8bb4e7;
}

.sea-cell {
  aspect-ratio: 1 / 1;
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
  transition: background-color 0.1s;
}

.sea-cell.cell-over-ship {
  background: transparent;
}

.sea-cell.clickable {
  cursor: crosshair;
}

.sea-cell.clickable:hover {
  background: rgba(52, 103, 159, 0.5);
}

.board-disabled .sea-cell.clickable {
  cursor: not-allowed;
}

.board-disabled .sea-cell.clickable:hover {
  background: #254b77;
}

.board-disabled .sea-cell.cell-over-ship:hover {
  background: transparent;
}

.sea-ship {
  position: relative;
  z-index: 1;
  pointer-events: none;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.sea-ship :deep(.battleship-svg) {
  position: absolute;
  inset: 0;
}

.sea-ship-preview {
  z-index: 1;
  pointer-events: none;
}

.sea-ship-revealed {
  opacity: 0.7;
}

.cell-miss {
  background: rgba(25, 49, 80, 0.6) !important;
}

.miss-icon {
  position: relative;
  z-index: 3;
  pointer-events: none;
  font-size: 1.4rem;
  color: #7a94b4;
  line-height: 1;
}

.cell-hit {
  background: rgba(139, 43, 36, 0.35) !important;
}

.hit-icon {
  position: relative;
  z-index: 3;
  pointer-events: none;
  font-size: 1.1rem;
  line-height: 1;
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
</style>

