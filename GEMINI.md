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
Nền tảng chơi trò chơi qua LAN: engine Python (`*_game.py`), máy chủ FastAPI + WebSocket (`server/`),
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
- Web: không thêm router hay store ngoài; trạng thái chung ở `web/src/game.js`. Tiền tố `caro.` trong `localStorage` giữ lại vì tương thích.
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
  5. Form tạo phòng: tạo `web/src/components/create/Create<Trò>.vue` (gọi `createRoom` và `emit('created')` sau khi tạo).
  6. Danh mục sảnh & tiêu đề: thêm vào `GAMES` và `TITLES` trong `web/src/games.js`.
  7. Màn chơi: dùng composable `useRoomView()` từ `web/src/room.js` kết hợp component trong `web/src/components/room/` (InviteBox, PlayerList, RequestBox). Thêm nhánh hiển thị màn chơi trong `web/src/App.vue`.
  8. Kiểm thử: thêm `server/tests/test_<trò>.py` kiểm tra luật, bot, pvp và snapshot.
- **Trò một người (dò mìn, sudoku...)**:
  1. Kế thừa `SoloSession` trong `server/<trò>.py`, khai báo `GAME = "<tên>"`.
  2. Dùng `SoloManager(ttl)` quản lý ván đang chơi.
  3. Điểm và xếp hạng tự động lưu vào bảng `solo_scores` qua `auth.record_solo`, `auth.solo_leaderboard`, `auth.solo_best`.
  4. Giao diện: thêm API riêng ở server, thêm thẻ trò chơi vào mục "Chơi một mình" trong hộp thoại tạo phòng (`HubView.vue`), tạo view riêng trong `web/src/components/`.
  5. Kiểm thử: thêm test trong `server/tests/test_<trò>.py`.

## Quy tắc giao diện & Frontend
- CSS màn chơi dùng chung chỉ nằm trong phạm vi `.room-view` của `style.css`.
- Class mới phải đặt tên riêng có tiền tố (như `.hub-*`, `.sea-*`) và đặt trong `<style scoped>`, không đặt class trùng tên toàn cục.
- Giữ nguyên chữ hiển thị và các phím tắt/sự kiện gắn vào bàn cờ khi tái cấu trúc.
- Giữ các quy tắc bàn Hải chiến đã chuẩn hóa: tàu vẽ bằng SVG absolute nằm trên ô (ô không z-index), không làm giãn lưới khi hover, fitOnBoard khi chuột sát mép.

## Bảo mật & Chống gian lận
- Máy chủ luôn giữ trạng thái bí mật (vị trí mìn, tàu chưa chìm, lời giải sudoku); không gửi cho client khi ván chưa kết thúc.
- Mọi thời gian tính điểm/kỷ lục đo bằng `time.monotonic()` ở máy chủ.
- Kiểm tra nghiêm ngặt kiểu dữ liệu đầu vào: dữ liệu sai kiểu (list/dict thay vì int/str) phải báo lỗi 400 hoặc `GameError`, tuyệt đối không để crash 500.

## Khi xong
Trả lời ngắn: đã sửa file nào, vì sao, test nào đã thêm, và điều gì chưa làm hoặc chưa chắc.
Không cần chạy test hay build: Claude sẽ chạy.
