<script setup>
import { reactive } from 'vue'
import { createRoom, state, X, O } from '../../game.js'

defineProps({
  info: { type: Object, default: () => ({ levels: [] }) },
})

const emit = defineEmits(['created'])

const bot = reactive({ level: 1, side: X, size: 15, strict: false })
const pvp = reactive({ size: 15, strict: false })
const SIZES = [9, 15, 30, 50]

function startBot() {
  createRoom({
    mode: 'bot',
    level: bot.level,
    side: bot.side,
    rows: bot.size,
    cols: bot.size,
    strict: bot.strict,
  })
  emit('created')
}

function startPvp() {
  createRoom({
    mode: 'pvp',
    rows: pvp.size,
    cols: pvp.size,
    strict: pvp.strict,
  })
  emit('created')
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
            v-for="level in info.levels || []"
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
          <button :class="{ active: bot.side === X }" @click="bot.side = X">X · đi trước</button>
          <button :class="{ active: bot.side === O }" @click="bot.side = O">O · máy đi trước</button>
        </div>
      </div>
      <label class="field">
        <span>Kích thước bàn</span>
        <select v-model.number="bot.size" class="input">
          <option v-for="n in SIZES" :key="n" :value="n">{{ n }} × {{ n }}</option>
        </select>
      </label>
      <label class="check">
        <input v-model="bot.strict" type="checkbox" />
        <span>Luật chặn hai đầu (bị chặn hai đầu thì không thắng)</span>
      </label>
      <button class="btn green block" :disabled="!state.connected" @click="startBot">
        Bắt đầu ván với máy
      </button>
    </div>

    <div class="card subcard">
      <h2>👥 Chơi với người (mạng LAN)</h2>
      <label class="field">
        <span>Kích thước bàn</span>
        <select v-model.number="pvp.size" class="input">
          <option v-for="n in SIZES" :key="n" :value="n">{{ n }} × {{ n }}</option>
        </select>
      </label>
      <label class="check">
        <input v-model="pvp.strict" type="checkbox" />
        <span>Luật chặn hai đầu</span>
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

