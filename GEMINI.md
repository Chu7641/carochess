# Hướng dẫn cho Gemini CLI trong project này

Bạn là người viết code; Claude Code giao việc, kiểm tra diff và chạy test sau khi bạn xong.
Làm đúng phạm vi đề bài, không thêm tính năng, tùy chọn hay thư viện không được yêu cầu.

## Không được làm
- Không commit, push, tạo nhánh hay chạy lệnh git làm thay đổi repo.
- Không đọc, sửa hay in nội dung `.env` và thư mục `data/` (mật khẩu và database thật).
- Không sửa `.venv/`, `web/node_modules/`, `web/dist/`.
- Không thêm dependency mới (Python hay npm) trừ khi đề bài cho phép.
- Không xóa hay sửa test có sẵn để cho qua; nếu test cũ không còn đúng, nói rõ lý do trong câu trả lời.

## Project
Cờ caro chơi qua LAN: engine Python (`caro_game.py`), máy chủ FastAPI + WebSocket (`server/`),
giao diện Vue 3 + Vite (`web/src/`), tài khoản SQLite (`server/auth.py`).
Đọc thêm trước khi sửa:
- `.claude/skills/caro-dev/SKILL.md`: cấu trúc, lệnh chạy, quy ước server/web.
- `.claude/skills/caro-engine/SKILL.md`: bất biến của engine bot (bắt buộc đọc nếu sửa `caro_game.py`).
- Giao thức WebSocket: docstring đầu `server/app.py`.

## Quy ước
- Thông báo cho người dùng, chữ trên giao diện và comment viết bằng **tiếng Việt có dấu**.
- Viết giống code xung quanh: cùng cách đặt tên, mật độ comment, kiểu viết. Comment chỉ giải thích "vì sao".
- Server: lỗi do người chơi thì `raise GameError("…")` hoặc `HTTPException(400, "…")`;
  mọi thay đổi trạng thái phòng phải đi qua `hub.changed(room)`.
- API chỉ admin dùng: thêm `Depends(current_admin)`. Không tin dữ liệu từ client.
- Web: không thêm router hay store ngoài; trạng thái chung ở `web/src/game.js`.
- Logic mới không tầm thường thì thêm test trong `server/tests/`: test nằm theo từng file trò
  (`test_caro.py`, `test_go.py`, `test_xiangqi.py`, `test_battleship.py`, `test_mines.py`, `test_sudoku.py`...);
  helper dùng chung nằm ở `server/tests/conftest.py` (fixture `client`, hàm `account()`, `login()`, `start()`...).
  Khi thêm trò mới thì tạo file `test_<trò>.py` riêng.

## Thêm trò mới
- **Trò đối kháng (caro, go, xiangqi, battleship...)**:
  1. Engine: viết trong `<trò>_game.py` ở thư mục gốc (luật, trạng thái, self-test).
  2. Phòng: tạo `server/<trò>_room.py` kế thừa `Room`, gọi `init_common()`, khai báo `game_type` và `actions` (hoặc `move_error`), tạo `snapshot()` = `base_snapshot()` + trường riêng.
  3. Bot: tạo `server/<trò>_bot.py` kế thừa `ThreadedBotDriver` (override `make_input`, `compute`, `apply`, `can_think` nếu cần).
  4. Đăng ký: khai báo `GameSpec` trong `server/games.py: GAMES`.
  5. Kiểm thử: thêm `server/tests/test_<trò>.py` kiểm tra luật, bot, pvp và snapshot.
- **Trò một người (dò mìn, sudoku...)**:
  1. Kế thừa `SoloSession` trong `server/<trò>.py`, khai báo `GAME = "<tên>"`.
  2. Dùng `SoloManager(ttl)` quản lý ván đang chơi.
  3. Điểm và xếp hạng tự động lưu vào bảng `solo_scores` qua `auth.record_solo`, `auth.solo_leaderboard`, `auth.solo_best`.
  4. Kiểm thử: thêm test trong `server/tests/test_<trò>.py`.

## Khi xong
Trả lời ngắn: đã sửa file nào, vì sao, test nào đã thêm, và điều gì chưa làm hoặc chưa chắc.
Không cần chạy test hay build: Claude sẽ chạy.
