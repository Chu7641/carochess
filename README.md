# Cờ caro · Gomoku

Cờ caro chơi trên trình duyệt trong mạng LAN, có hai chế độ: **người đấu người** và
**người đấu máy**. Bot viết bằng Python thuần, không dùng thư viện AI hay dịch vụ mạng.
Project có kèm bản desktop (pygame) dùng chung engine.

- **Đấu máy:** 3 mức độ khó (Nhanh 2 giây, Mạnh 5 giây, Chuyên gia 12 giây mỗi nước).
  Bạn chọn cầm X (đi trước) hoặc O (máy đi trước). Hoàn tác được.
- **Đấu người qua LAN:** tạo phòng có mã 4 ký tự và link mời, xem danh sách phòng đang chờ.
  Người thứ ba vào phòng sẽ là người xem. Mỗi ván mới hai bên đổi quân.
- **Bàn cờ:** bản web từ 9×9 đến 50×50 (bàn lớn thì cuộn được, có phóng to/thu nhỏ và
  tự đưa nước mới vào tầm nhìn); bản desktop từ 9×9 đến 25×25.
- **Luật:** 5 quân liên tiếp là thắng. Có thể bật luật chặn hai đầu
  (dãy bị chặn cả hai đầu thì không thắng). Đây không phải luật Renju.
- Tải lại trang hoặc mất mạng giữa ván thì tự kết nối lại và giữ đúng ghế cũ.
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
```

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
.venv\Scripts\python.exe -m pytest server           # máy chủ: phòng, WebSocket, bot
```

## Cấu trúc

```
caro_game.py          Engine (luật, bot) + game desktop pygame
server/
  app.py              FastAPI: WebSocket /ws, /api/info, /api/rooms, phục vụ web/dist
  game.py             Phòng chơi: ghế, luật, hoàn tác, đổi bên
  bot.py              Chạy bot ở luồng nền cho mỗi phòng, có nghĩ trước
  tests/              Kiểm thử máy chủ (pytest)
web/
  src/game.js         Kết nối WebSocket, trạng thái, tự kết nối lại
  src/components/     LobbyView (sảnh), GameView (ván cờ), CaroBoard (bàn cờ SVG)
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
- Chế độ đấu người chưa có hoàn tác, chat hay đồng hồ.
- Không có đăng nhập; chỉ nên chạy trong mạng LAN tin cậy, không đưa thẳng ra Internet.
