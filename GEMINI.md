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

## Khi xong
Trả lời ngắn: đã sửa file nào, vì sao, test nào đã thêm, và điều gì chưa làm hoặc chưa chắc.
Không cần chạy test hay build: Claude sẽ chạy.
