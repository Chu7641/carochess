---
name: caro-dev
description: Chạy, build và kiểm thử project cờ caro (game desktop pygame, máy chủ FastAPI chơi qua LAN, giao diện Vue 3 + Vite). Dùng khi cần khởi động app, chạy dev server, build web, chạy test, hoặc khi sửa server/ hay web/ và cần biết cấu trúc, giao thức WebSocket.
---

# Project cờ caro: cách chạy và cấu trúc

Mọi lệnh chạy từ thư mục gốc `F:\4.Project\carochess`, dùng Python trong `.venv`
(`.venv\Scripts\python.exe`). Không dùng Python hệ thống.

## Cấu trúc
- `caro_game.py`: engine (luật, `Position`, `CaroBot` với VCF/VCT/ponder) + game desktop pygame.
  pygame chỉ được import trong `CaroGame.__init__`, nên server và test không cần màn hình.
- Đăng nhập: `server/auth.py` (SQLite `data/caro.db`, admin từ `.env`, cookie `session`).
  `/ws` và `/api/*` (trừ login/register) yêu cầu đăng nhập; ghế trong phòng khóa theo tên tài khoản.
  Test server tự tạo DB tạm và tài khoản qua fixture `client` + `account()`.
- `server/`: FastAPI. `game.py` = `Room` (ghế, luật, hoàn tác, đổi bên); `bot.py` = `BotDriver`
  (chạy `CaroBot` ở luồng nền, có nghĩ trước); `app.py` = `Hub`, WebSocket `/ws`, `/api/info`,
  `/api/rooms`, phục vụ `web/dist`. Giao thức tin nhắn ghi ở docstring đầu `server/app.py`.
- `web/`: Vue 3 + Vite, không router/store ngoài. `src/game.js` giữ kết nối WebSocket và
  trạng thái tài khoản (tự kết nối lại). Màn hình: `LoginView` → `GamesView` (chọn trò,
  thêm trò mới ở mảng `GAMES`) → `LobbyView` → `GameView` + `CaroBoard` (SVG).

## Lệnh
| Việc | Lệnh |
|---|---|
| Cài Python deps | `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` |
| Cài web deps | `npm install` trong `web/` |
| Chạy bản LAN (production) | `npm run build` trong `web/`, rồi `.venv\Scripts\python.exe -m server` → cổng 8000, nghe 0.0.0.0, in ra IP LAN |
| Phát triển web | Terminal 1: `.venv\Scripts\python.exe -m server --reload`; Terminal 2: `npm run dev` trong `web/` (cổng 5173, proxy `/api` và `/ws` sang 8000) |
| Game desktop | `.venv\Scripts\python.exe caro_game.py` |
| Test engine | `.venv\Scripts\python.exe caro_game.py --self-test` |
| Test server | `.venv\Scripts\python.exe -m pytest server` |

Chạy server bằng `run_in_background`; muốn dừng thì tắt tiến trình đang nghe cổng 8000.
Kiểm tra nhanh: `GET /api/info` và mở một WebSocket tới `/ws` (gói `websockets` có sẵn trong venv).

## Quy ước khi sửa
- Luật thắng chỉ có một nguồn: `winning_line` trong `caro_game.py`; server không tự viết lại luật.
- X luôn đi trước. Đấu máy: người chọn X hoặc O. PvP: mỗi ván mới hai ghế đổi bên.
- Mỗi thay đổi bàn cờ ở server phải qua `Hub.changed(room)` (gọi `BotDriver.sync` rồi gửi state);
  hoàn tác và ván mới dùng `reset_bot=True`.
- Lỗi của người chơi: raise `GameError` với câu tiếng Việt; câu đó được gửi nguyên văn cho client.
- Giao diện, thông báo và comment viết bằng tiếng Việt, giống phần code hiện có.
- Sau khi sửa server hoặc web: chạy cả hai bộ test, rồi `npm run build`.
