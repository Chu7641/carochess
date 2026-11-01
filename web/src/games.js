export const GAMES = [
  { id: 'caro', name: 'Cờ caro', icon: '⚫🔴', desc: '5 quân liên tiếp là thắng. Đấu với máy hoặc với bạn trong mạng LAN.', kind: 'room' },
  { id: 'go', name: 'Cờ vây', icon: '⚪⚫', desc: 'Vây bắt quân và chiếm đất. Hỗ trợ bàn 9×9, 13×13, 19×19 qua LAN hoặc đấu với máy.', kind: 'room' },
  { id: 'xiangqi', name: 'Cờ tướng', icon: '帥將', desc: 'Đấu trí trên chiến trường Hán - Sở. Đấu với máy các cấp độ từ Dễ đến Khó.', kind: 'room' },
  { id: 'battleship', name: 'Hải chiến', icon: '🚢', desc: 'Bố trí 5 chiến hạm và truy quét hạm đội đối phương trên biển 10×10. Bắn trúng được bắn tiếp.', kind: 'room' },
  { id: 'minesweeper', name: 'Dò mìn', icon: '💣', desc: 'Dò tìm và cắm cờ toàn bộ bãi mìn kiểu Windows cổ điển. Bảng xếp hạng thời gian.', kind: 'solo' },
  { id: 'sudoku', name: 'Sudoku', icon: '🔢', desc: 'Điền các chữ số 1–9 vào bảng 9×9 sao cho không trùng hàng, cột và khối 3×3. Bảng xếp hạng.', kind: 'solo' },
]

export const TITLES = {
  caro: 'CỜ CARO · GOMOKU',
  go: 'CỜ VÂY · GO / BADUK',
  xiangqi: 'CỜ TƯỚNG · XIANGQI',
  minesweeper: 'DÒ MÌN · MINESWEEPER',
  sudoku: 'SUDOKU',
  battleship: 'HẢI CHIẾN · BATTLESHIP',
  leaderboard: 'BẢNG XẾP HẠNG',
  admin: 'QUẢN TRỊ',
  password: 'TÀI KHOẢN',
}

