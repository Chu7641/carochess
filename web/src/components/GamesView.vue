<script setup>
import { chooseGame } from '../game.js'

// Thêm trò mới: thêm một dòng ở đây và một nhánh hiển thị trong App.vue.
const GAMES = [
  { id: 'caro', name: 'Cờ caro', icon: '⚫🔴', desc: '5 quân liên tiếp là thắng. Đấu với máy hoặc với bạn trong mạng LAN.' },
  { id: 'go', name: 'Cờ vây', icon: '⚪⚫', desc: 'Vây bắt quân và chiếm đất. Hỗ trợ bàn 9×9, 13×13, 19×19 qua LAN hoặc đấu với máy.' },
  { id: 'xiangqi', name: 'Cờ tướng', icon: '帥將', desc: 'Đấu trí trên chiến trường Hán - Sở. Đấu với máy các cấp độ từ Dễ đến Khó.' },
  { id: 'minesweeper', name: 'Dò mìn', icon: '💣', desc: 'Dò tìm và cắm cờ toàn bộ bãi mìn kiểu Windows cổ điển. Bảng xếp hạng thời gian.' },
  { id: 'sudoku', name: 'Sudoku', icon: '🔢', desc: 'Điền các chữ số 1–9 vào bảng 9×9 sao cho không trùng hàng, cột và khối 3×3. Bảng xếp hạng.' },
  { id: 'battleship', name: 'Hải chiến', icon: '🚢', desc: 'Bố trí 5 chiến hạm và truy quét hạm đội đối phương trên biển 10×10. Bắn trúng được bắn tiếp.' },
]
</script>

<template>
  <section>
    <h2 class="title">Chọn công cụ</h2>
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
