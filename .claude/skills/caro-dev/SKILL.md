---
name: caro-dev
description: Chạy, build và kiểm thử project chơi nhiều trò qua LAN (caro, cờ vây, cờ tướng, hải chiến, dò mìn, sudoku; máy chủ FastAPI + giao diện Vue 3 + Vite; bản desktop pygame cho caro). Dùng khi cần khởi động app, chạy dev server, build web, chạy test, hoặc khi sửa server/ hay web/ và cần biết cấu trúc, giao thức WebSocket.
---

# Project chơi trò qua LAN: cách chạy và cấu trúc

Mọi lệnh chạy từ thư mục gốc `F:\4.Project\carochess`, dùng Python trong `.venv`
(`.venv\Scripts\python.exe`). Không dùng Python hệ thống.

## Cấu trúc
- Engine ở thư mục gốc, mỗi file có `--self-test`: `caro_game.py` (kèm game desktop pygame, chỉ import
  pygame trong `CaroGame.__init__`), `go_game.py`, `xiangqi_game.py`, `battleship_game.py`,
  `minesweeper_game.py`, `sudoku_game.py`.
- `server/`:
  - `app.py`: `Hub`, WebSocket `/ws`, các `/api/*`, phục vụ `web/dist`. Giao thức ghi ở docstring đầu file.
  - `games.py`: sổ đăng ký `GAMES` (lớp phòng + bot cho mỗi trò có phòng). Thêm trò: xem `GEMINI.md`.
  - `game.py`: `Room` gốc (ghế, sẵn sàng, đồng hồ, xin đi lại, `actions`, `base_snapshot`) = phòng caro.
    `*_room.py` kế thừa `Room`.
  - `bot.py`: bot caro (có nghĩ trước). `bot_driver.py`: `ThreadedBotDriver` cho bot cờ vây/cờ tướng/hải chiến
    (`*_bot.py`). Giữ nguyên `_worker_exited` (join rồi `sync`) và việc bỏ kết quả của `cancel_event` cũ: đó là sửa lỗi bot treo.
  - `solo.py`: `SoloSession`/`SoloManager` cho trò một người (`mines.py`, `sudoku.py`), điểm ở bảng `solo_scores`.
  - `auth.py`: SQLite `data/caro.db`, admin từ `.env`, cookie `session`, elo, bảng xếp hạng.
  - `tests/`: mỗi trò một file `test_<trò>.py`, helper chung ở `conftest.py` (fixture `client`, `account()`...).
- `web/src/`: Vue 3, không router/store ngoài. `game.js` = WebSocket + trạng thái (`state.game`: null = sảnh,
  hoặc 'minesweeper' | 'sudoku' | 'leaderboard' | 'admin' | 'password'; trong phòng thì màn chơi theo `state.room.game`).
  `games.js` = danh sách trò + tiêu đề. `HubView.vue` = sảnh lưới ô + hộp tạo phòng (`create/Create<Trò>.vue`).
  Màn chơi `*GameView.vue` dùng `room.js` (`useRoomView`) và `components/room/*`; hải chiến tách trong `components/battleship/`.

## Lệnh
| Việc | Lệnh |
|---|---|
| Cài Python deps | `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` |
| Cài web deps | `npm install` trong `web/` |
| Chạy bản LAN | `npm run build` trong `web/`, rồi `.venv\Scripts\python.exe -m server` → cổng 8000, nghe 0.0.0.0 |
| Phát triển web | Terminal 1: `.venv\Scripts\python.exe -m server --reload`; Terminal 2: `npm run dev` trong `web/` (cổng 5173) |
| Game desktop | `.venv\Scripts\python.exe caro_game.py` |
| Test engine | `.venv\Scripts\python.exe <trò>_game.py --self-test` (6 file) |
| Test server | `.venv\Scripts\python.exe -m pytest server` (hoặc một file `server/tests/test_<trò>.py`) |

Chạy server bằng `run_in_background`. Kiểm tra treo: `pytest ... -o faulthandler_timeout=60`.

## Quy ước khi sửa
- Mỗi thay đổi phòng ở server phải qua `Hub.changed(room)`; hoàn tác và ván mới dùng `reset_bot=True`.
- Lỗi của người chơi: raise `GameError` với câu tiếng Việt, gửi nguyên văn cho client. Dữ liệu sai kiểu
  (list/dict/chuỗi thay vì số) phải ra `GameError`/400, không được 500 hay rớt WebSocket.
- Không gửi thông tin ẩn cho client: tàu chưa chìm, vị trí mìn, lời giải sudoku.
- CSS màn chơi dùng chung nằm trong `.room-view` (style.css); class mới đặt tiền tố riêng và scoped.
  Chữ hiển thị "KHÔNG GIAN LÀM VIỆC" / "Chọn công cụ" / tiêu đề tab "Test AI local" là ngụy trang có chủ đích.
- Giao diện, thông báo và comment viết bằng tiếng Việt.
- Sau khi sửa: chạy self-test liên quan, `pytest server`, rồi `npm run build`.
