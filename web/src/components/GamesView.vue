<script setup>
import { chooseGame } from '../game.js'

// Thêm trò mới: thêm một dòng ở đây và một nhánh hiển thị trong App.vue.
const GAMES = [
  { id: 'caro', name: 'Cờ caro', icon: '⚫🔴', desc: '5 quân liên tiếp là thắng. Đấu với máy hoặc với bạn trong mạng LAN.' },
]
</script>

<template>
  <section>
    <h2 class="title">Chọn trò chơi</h2>
    <div class="games">
      <button v-for="game in GAMES" :key="game.id" class="card game" @click="chooseGame(game.id)">
        <span class="icon" aria-hidden="true">{{ game.icon }}</span>
        <strong>{{ game.name }}</strong>
        <span class="small muted">{{ game.desc }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.title { max-width: 920px; margin: 8px auto 16px; }
.games {
  max-width: 920px;
  margin: 0 auto;
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}
.game {
  display: grid;
  gap: 8px;
  text-align: left;
  color: var(--text);
  cursor: pointer;
  transition: transform 0.1s, border-color 0.15s;
}
.game:hover { transform: translateY(-2px); border-color: var(--green); }
.icon { font-size: 2rem; }
</style>
