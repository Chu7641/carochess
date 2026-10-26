# Cờ caro · Gomoku

Cờ caro chơi trên trình duyệt trong mạng LAN, có hai chế độ: **người đấu người** và
**người đấu máy**. Bot viết bằng Python thuần, không dùng thư viện AI hay dịch vụ mạng.
Project có kèm bản desktop (pygame) dùng chung engine.

- **Tài khoản:** đăng ký/đăng nhập, lưu trong SQLite (`data/caro.db`). Tài khoản mới phải
  được admin phê duyệt mới đăng nhập được. Bấm vào tên mình trên thanh tiêu đề để đổi mật khẩu.
  Đăng nhập xong thì chọn trò chơi: cờ caro, cờ vây hoặc cờ tướng.
- **Cờ tướng:** hỗ trợ cả đấu người qua LAN và đấu với máy (3 mức: Dễ 0,5 giây, Vừa 1,5 giây, Khó 4 giây mỗi nước;
  bot alpha-beta). Đấu người dùng chung sẵn sàng, đồng hồ 30 giây, tính elo, xin đi lại. Đủ luật: cản chân Mã,
  cản mắt Tượng, Pháo ăn qua ngòi, lộ mặt tướng; hết nước đi là thua, lặp thế cờ 3 lần là hòa (chưa có luật cấm chiếu mãi, đuổi mãi).
  Bấm quân để thấy các ô đi được, tự động lật bàn cờ khi cầm Đen.
- **Cờ vây:** bàn 9×9, 13×13, 19×19, có bắt quân, cấm tự sát, luật Kiếp, bỏ lượt và
  đếm điểm diện tích kèm komi (chưa tự loại quân chết: hãy bắt hết trước khi cùng bỏ lượt).
  Đấu người dùng chung sẵn sàng, đồng hồ, elo; đấu máy có 3 mức (bot Monte Carlo, mạnh nhất ở 9×9).
- **Dò mìn:** chơi một người theo phong cách Windows cổ điển. 3 mức độ (Dễ 9×9 10 mìn, Vừa 16×16 40 mìn, Khó 16×30 99 mìn).
  Cơ chế chống gian lận: máy chủ giữ vị trí mìn và tự đo thời gian chuẩn xác bằng `time.monotonic()`.
  Lần mở đầu luôn an toàn và mở ra một vùng. Hỗ trợ mở lan (chording), cắm cờ (chuột phải hoặc giữ 400ms trên điện thoại),
  bảng xếp hạng thành tích thời gian tốt nhất của các tài khoản.
- **Quản trị:** tài khoản admin khai báo trong `.env`. Trang Quản trị: duyệt/từ chối đăng ký,
  xem người dùng, nâng lên admin, đặt lại mật khẩu (sinh ngẫu nhiên), reset elo, xóa tài khoản.
- **Đấu máy:** 3 mức độ khó (Nhanh 2 giây, Mạnh 5 giây, Chuyên gia 12 giây mỗi nước).
  Bạn chọn cầm X (đi trước) hoặc O (máy đi trước). Hoàn tác được. Không tính elo.
- **Đấu người qua LAN:** tạo phòng có mã 4 ký tự và link mời. Sảnh hiện mọi phòng
  (đang chờ, đang chơi, đấu máy): bấm để vào chơi, vào lại ghế của mình, hoặc vào xem.
  - Đủ hai người thì cả hai bấm **Sẵn sàng** ván mới bắt đầu. Mỗi ván mới hai bên đổi quân.
  - Mỗi lượt có **30 giây**. Hết giờ, rời phòng hoặc bấm "Ván mới" khi ván chưa xong thì
    bị tính thua.
  - **Xin đi lại** cần đối thủ đồng ý.
  - **Elo:** bắt đầu 1000, tính theo Elo chuẩn K = 32 (hai người ngang điểm: thắng +16, thua −16).
- **Bàn cờ:** bản web từ 9×9 đến 50×50 (bàn lớn thì cuộn được, có phóng to/thu nhỏ và
  tự đưa nước mới vào tầm nhìn); bản desktop từ 9×9 đến 25×25.
- **Luật:** 5 quân liên tiếp là thắng. Có thể bật luật chặn hai đầu
  (dãy bị chặn cả hai đầu thì không thắng). Đây không phải luật Renju.
- Tải lại trang, mất mạng hay đổi máy giữa ván thì đăng nhập lại là về đúng ghế cũ.
  Giao diện dùng được trên điện thoại, có chế độ tối.

## Yêu cầu

- Python 3.10 trở lên
- Node.js 20.19+ hoặc 22.12+ (chỉ cần để build giao diện)

## Cài đặt

```bash
git clone https://github.com/Chu7641/carochess.git
cd carochess

python -m venv .venv
# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt

cd web
npm install
npm run build
cd ..

# Khai báo tài khoản admin, rồi sửa ADMIN_PASSWORD trong .env
copy .env.example .env      # macOS / Linux: cp .env.example .env
```

Tài khoản admin được tạo ở lần chạy máy chủ đầu tiên; đăng nhập bằng `ADMIN_USERNAME` và
`ADMIN_PASSWORD` trong `.env`. Sửa `ADMIN_PASSWORD` sau lần chạy đầu không đổi mật khẩu của
tài khoản đã tạo. `.env` và thư mục `data/` không được đưa lên git.

Các lệnh bên dưới viết theo Windows. Trên macOS/Linux, thay `.venv\Scripts\python.exe`
bằng `.venv/bin/python`.

## Chạy

```bash
.venv\Scripts\python.exe -m server
```

Máy chủ nghe trên mọi card mạng ở cổng 8000 và in ra địa chỉ để truy cập:

```
Cờ caro LAN đang chạy. Mở trên máy này: http://localhost:8000
  Máy khác cùng mạng LAN: http://192.168.1.19:8000
```

Máy khác trong cùng mạng mở địa chỉ LAN đó trên trình duyệt. Lần đầu chạy trên Windows, khi
được hỏi về tường lửa, hãy cho phép Python trên mạng **Private**. Nếu máy khác vẫn không
truy cập được, mở cổng 8000 trong Windows Firewall.

Tùy chọn: `--port 9000` để đổi cổng, `--host 127.0.0.1` để chỉ cho chính máy này truy cập.

### Bản desktop

```bash
.venv\Scripts\python.exe caro_game.py
```

Chuột trái: đánh. Chuột phải / U: hoàn tác. R: ván mới. F: đổi quân đi trước.
S: đổi bên bot. B: bật/tắt luật chặn hai đầu. P: bật/tắt nghĩ trước. 1/2/3: độ khó.
+/-: đổi kích thước bàn. Esc: thoát.

## Phát triển

Chạy song song hai terminal:

```bash
# Terminal 1: máy chủ Python, tự khởi động lại khi sửa code
.venv\Scripts\python.exe -m server --reload

# Terminal 2: giao diện Vue có hot reload tại http://localhost:5173
cd web
npm run dev
```

Vite chuyển tiếp `/api` và `/ws` sang cổng 8000. Sửa giao diện xong, chạy `npm run build`
để máy chủ phục vụ bản mới.

### Kiểm thử

```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

.venv\Scripts\python.exe caro_game.py --self-test   # engine: luật, VCF/VCT, make/unmake
.venv\Scripts\python.exe go_game.py --self-test     # cờ vây: luật, đếm điểm, bot
.venv\Scripts\python.exe xiangqi_game.py --self-test   # cờ tướng: luật, perft, bot
.venv\Scripts\python.exe minesweeper_game.py --self-test # dò mìn: luật, loang mở, chording
.venv\Scripts\python.exe -m pytest server           # máy chủ: phòng, WebSocket, bot, dò mìn
```

## Cấu trúc

```
caro_game.py          Engine (luật, bot) + game desktop pygame
go_game.py            Engine cờ vây: luật, đếm điểm, bot Monte Carlo
xiangqi_game.py       Engine cờ tướng: luật, bot alpha-beta
minesweeper_game.py   Engine trò chơi Dò mìn (Minesweeper)
GEMINI.md             Quy tắc cho agent viết code (Gemini/Antigravity CLI)
server/
  app.py              FastAPI: đăng nhập, WebSocket /ws, /api/rooms, /api/mines, phục vụ web/dist
  auth.py             Tài khoản + phiên đăng nhập + điểm dò mìn (SQLite, scrypt), đọc .env
  game.py             Phòng chơi: ghế, luật, hoàn tác, đổi bên
  mines.py            Quản lý các ván dò mìn đang chơi trong bộ nhớ
  bot.py              Chạy bot ở luồng nền cho mỗi phòng, có nghĩ trước
  go_room.py, go_bot.py  Phòng chơi và bot nền cho cờ vây
  xiangqi_room.py, xiangqi_bot.py  Phòng chơi và bot nền cho cờ tướng
  tests/              Kiểm thử máy chủ (pytest)
web/
  src/game.js         Tài khoản, kết nối WebSocket, trạng thái, tự kết nối lại
  src/components/     LoginView, GamesView (chọn trò), LobbyView (sảnh), GameView (ván cờ),
                      CaroBoard (bàn cờ SVG), AdminView (quản trị),
                      GoLobbyView / GoGameView / GoBoard (cờ vây),
                      XiangqiLobbyView / XiangqiGameView / XiangqiBoard (cờ tướng),
                      MinesweeperView (dò mìn)
.claude/skills/       Hướng dẫn cho Claude Code khi làm việc với project
```

Giao thức WebSocket được mô tả ở đầu file [server/app.py](server/app.py).

## Bot hoạt động thế nào

- **Tìm kiếm:** iterative deepening, alpha-beta/PVS, transposition table với khóa Zobrist,
  history heuristic. Mỗi dòng trên bàn được mã hóa thành một số cơ số 3 và cập nhật dần
  sau mỗi nước; đặc trưng của dòng được tra bảng, nên đánh giá thế cờ không phải duyệt lại
  cả bàn.
- **Chuỗi ép thắng:** VCF (ép liên tục bằng bốn) và VCT (ép bằng ba và bốn). Mỗi lần bên
  phòng thủ được đi, bot xét mọi cách đỡ hợp lệ, gồm cả phản công bằng bốn. Vì vậy khi bot
  báo "chuỗi ép thắng" thì đó là thắng chắc.
- **Nghĩ trước:** trong lượt của người chơi, bot đoán nước sẽ được đánh và tính sẵn nước đáp.
  Đoán trúng thì máy trả lời nhanh hơn và đã tính sâu hơn.
- Mức Chuyên gia đạt độ sâu khoảng 8 nước, tốc độ khoảng 8.000 nút mỗi giây (CPython).

Bot mạnh với người chơi thông thường nhưng **không bất bại**. Với luật tự do trên bàn 15×15,
người đi trước có lợi thế thắng về mặt lý thuyết (Allis, 1994). Muốn máy khó hơn, hãy để
máy đi trước.

## Giới hạn

- Bot của mọi phòng chạy chung một tiến trình Python. Nhiều ván đấu máy cùng lúc sẽ tranh
  CPU và mỗi bot tính nông hơn.
- Phòng nằm trong bộ nhớ: khởi động lại máy chủ thì mất các ván đang chơi. Phòng không còn ai
  kết nối sẽ bị xóa sau 10 phút.
- Chưa có chat, bảng xếp hạng hay lịch sử ván đấu.
- Quên mật khẩu thì nhờ admin đặt lại (chưa có khôi phục qua email).
- Đăng nhập chưa giới hạn số lần thử sai, và chạy HTTP thường (không HTTPS). Chỉ nên
  chạy trong mạng LAN tin cậy, không đưa thẳng ra Internet.
