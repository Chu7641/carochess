<script setup>
import { reactive, watch } from 'vue'
import { createRoom, state } from '../../game.js'

defineProps({
  info: { type: Object, default: () => ({ goLevels: [], goSizes: [9, 13, 19] }) },
})

const DEFAULT_KOMI = { 9: 5.5, 13: 6.5, 19: 7.5 }
const SIZES = [9, 13, 19]

const bot = reactive({ level: 1, side: 1, size: 19 })
const pvp = reactive({ size: 19, komi: 7.5 })

watch(() => pvp.size, (s) => {
  pvp.komi = DEFAULT_KOMI[s] ?? 7.5
})

function startBot() {
  createRoom({
    game: 'go',
    mode: 'bot',
    level: bot.level,
    side: bot.side,
    size: bot.size,
  })
}

function startPvp() {
  createRoom({
    game: 'go',
    mode: 'pvp',
    size: pvp.size,
    komi: pvp.komi,
  })
}
</script>

<template>
  <div class="create-forms">
    <div class="card subcard">
      <h2>🤖 Chơi với máy</h2>
      <div class="field">
        <span>Độ khó</span>
        <div class="segmented">
          <button
            v-for="level in info.goLevels || []"
            :key="level.id"
            :class="{ active: bot.level === level.id }"
            @click="bot.level = level.id"
          >
            {{ level.name }} <small class="muted-on">· {{ level.seconds }}s</small>
          </button>
        </div>
      </div>
      <div class="field">
        <span>Bạn cầm quân</span>
        <div class="segmented">
          <button :class="{ active: bot.side === 1 }" @click="bot.side = 1">⚫ Đen · đi trước</button>
          <button :class="{ active: bot.side === 2 }" @click="bot.side = 2">⚪ Trắng · đi sau</button>
        </div>
      </div>
      <div class="field">
        <span>Kích thước bàn</span>
        <div class="segmented">
          <button
            v-for="n in SIZES"
            :key="n"
            :class="{ active: bot.size === n }"
            @click="bot.size = n"
          >
            {{ n }} × {{ n }}
          </button>
        </div>
      </div>
      <button class="btn green block" :disabled="!state.connected" @click="startBot">
        Bắt đầu ván với máy
      </button>
    </div>

    <div class="card subcard">
      <h2>👥 Chơi với người (mạng LAN)</h2>
      <div class="field">
        <span>Kích thước bàn</span>
        <div class="segmented">
          <button
            v-for="n in SIZES"
            :key="n"
            :class="{ active: pvp.size === n }"
            @click="pvp.size = n"
          >
            {{ n }} × {{ n }}
          </button>
        </div>
      </div>
      <label class="field">
        <span>Điểm mục chấp (Komi)</span>
        <input v-model.number="pvp.komi" class="input" type="number" step="0.5" />
      </label>
      <button class="btn blue block" :disabled="!state.connected" @click="startPvp">
        Tạo phòng mới
      </button>
    </div>
  </div>
</template>

<style scoped>
.create-forms { display: grid; gap: 14px; }
.subcard { background: var(--bg); border: 1px solid var(--panel-border); }
.muted-on { opacity: 0.75; font-size: 0.75rem; }
</style>

