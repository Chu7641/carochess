# Nền tảng trò chơi qua mạng LAN

Nền tảng chơi nhiều trò chơi qua trình duyệt trong mạng LAN (hỗ trợ tài khoản, sảnh chung dạng lưới ô, đấu người và đấu máy, tính điểm Elo, bảng xếp hạng), kèm bản desktop pygame cho cờ caro. Bot viết bằng Python thuần, không phụ thuộc thư viện AI hay dịch vụ mạng bên ngoài.

## Các trò chơi

- **Cờ caro:** 5 quân liên tiếp là thắng, hỗ trợ bật/tắt luật chặn hai đầu. Bàn cờ từ 9×9 đến 50×50 (bàn lớn có cuộn, zoom và tự cuộn theo nước mới). Đấu máy 3 mức (Nhanh 2s, Mạnh 5s, Chuyên gia 12s, có tính năng nghĩ trước); đấu người qua LAN có đồng hồ 30 giây, tính elo, xin đi lại và đổi quân mỗi ván.
- **Cờ vây:** Hỗ trợ kích thước bàn 9×9, 13×13, 19×19, đủ luật bắt quân, cấm tự sát, luật Kiếp, bỏ lượt và đếm điểm diện tích kèm điểm mục chấp (komi). Đấu người dùng chung đồng hồ và tính elo; đấu máy có 3 mức dựa trên thuật toán Monte Carlo.
- **Cờ tướng:** Tái hiện chiến trường Hán - Sở với đủ luật cản chân Mã, cản mắt Tượng, Pháo ăn qua ngòi, lộ mặt tướng, lặp thế cờ 3 lần xử hòa. Tự động lật bàn cờ khi cầm quân Đen. Đấu máy 3 mức (Dễ 0,5s, Vừa 1,5s, Khó 4s dùng alpha-beta); đấu người qua LAN hỗ trợ đồng hồ 30s, elo và xin đi lại.
- **Hải chiến (Battleship):** Bàn cờ 10×10 mỗi bên, hạm đội gồm 5 chiến hạm (Tàu sân bay 5, Thiết giáp hạm 4, Tuần dương hạm 3, Tàu ngầm 3, Khu trục hạm 2). Xếp tàu tự do (được nằm sát nhau), bắn trúng hoặc đánh chìm được bắn tiếp, trượt mất lượt:
  - Đấu máy 3 mức: Dễ (ngẫu nhiên + quét lân cận), Vừa (quét ô chẵn lẻ + theo trục), Khó (bản đồ mật độ xác suất và truy kích cụm tàu).
  - Đấu người qua LAN: Mỗi bên xếp tàu bí mật; cả hai xếp xong ván bắt đầu (Bên 1 bắn trước). Đồng hồ 30s mỗi lượt, tính elo, đổi bên sau mỗi ván; người xem theo dõi được cả 2 bàn cờ song song.
  - Chống gian lận/lộ thông tin: Client chỉ nhận tọa độ phát bắn và tàu đối phương đã chìm; vị trí tàu chưa chìm chỉ được tiết lộ khi ván đấu kết thúc.
- **Dò mìn:** Chơi một người theo phong cách Windows cổ điển với 3 mức độ (Dễ 9×9 10 mìn, Vừa 16×16 40 mìn, Khó 16×30 99 mìn). Lần mở đầu luôn an toàn, hỗ trợ mở lan (chording), cắm cờ (chuột phải hoặc giữ 400ms trên màn hình cảm ứng). Máy chủ giữ lời giải và tự bấm giờ chống gian lận.
- **Sudoku:** Chơi một người điền các chữ số 1–9 vào lưới 9×9 sao cho không trùng hàng, cột và khối 3×3 (3 độ khó: Dễ, Vừa, Khó). Máy chủ sinh đề duy nhất, tự bấm giờ, lưu kỷ lục cá nhân và xếp hạng thời gian; hỗ trợ tính năng gợi ý nước đi (không tính kỷ lục).

## Tính năng hệ thống

- **Tài khoản & Phân quyền:** Đăng ký và đăng nhập bảo mật (lưu trong SQLite `data/caro.db`, băm mật khẩu scrypt). Tài khoản mới cần admin duyệt. Có thể tự đổi mật khẩu cá nhân.
- **Sảnh chung dạng lưới ô (Hub):** Hiển thị toàn bộ phòng đang mở, lọc nhanh theo trò, ô nhập mã phòng trực tiếp, cùng ô "Tạo phòng" nổi bật mở hộp thoại 2 bước (chọn trò chơi và thiết lập thông số ván đấu).
- **Bảng xếp hạng:** Theo dõi Top 50 Elo đối kháng trên toàn hệ thống và kỷ lục thời gian hoàn thành của các trò chơi một người (Dò mìn, Sudoku).
- **Quản trị:** Trang quản trị cho admin duyệt/từ chối đăng ký, quản lý người dùng, phân quyền admin, đặt lại mật khẩu ngẫu nhiên, reset elo hoặc xóa tài khoản.
- **Chơi qua mạng LAN & Đổi thiết bị:** Tải lại trang, mất kết nối hay đổi máy tính giữa ván thì đăng nhập lại sẽ tự động về đúng phòng và ghế đang ngồi. Giao diện tối ưu cho điện thoại di động và hỗ trợ chế độ tối (dark mode).

## Yêu cầu

- Python 3.10 trở lên
- Node.js 20.19+ hoặc 22.12+ (chỉ cần khi build giao diện web)

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

# Khai báo tài khoản admin ban đầu, sau đó sửa ADMIN_PASSWORD trong .env
copy .env.example .env      # macOS / Linux: cp .env.example .env
```

Tài khoản admin được tự động khởi tạo ở lần chạy máy chủ đầu tiên dựa trên `ADMIN_USERNAME` và `ADMIN_PASSWORD` trong `.env`. `.env` và thư mục `data/` không đưa lên kho git.
Các lệnh bên dưới viết theo Windows; trên macOS/Linux, thay `.venv\Scripts\python.exe` bằng `.venv/bin/python`.

## Chạy máy chủ

```bash
.venv\Scripts\python.exe -m server
```

Máy chủ lắng nghe trên mọi card mạng ở cổng 8000 và hiển thị thông tin truy cập:

```
Máy chủ đang chạy. Mở trên máy này: http://localhost:8000
  Máy khác cùng mạng LAN: http://192.168.1.19:8000
```

Các thiết bị khác trong cùng mạng LAN chỉ cần mở trình duyệt và truy cập địa chỉ IP hiển thị ở trên. Lần đầu chạy trên Windows, hãy cấp quyền tường lửa cho Python trên mạng **Private**.

Tùy chọn: `--port 9000` để đổi cổng, `--host 127.0.0.1` nếu chỉ muốn chơi cục bộ trên máy này.

### Bản desktop (Cờ caro)

```bash
.venv\Scripts\python.exe caro_game.py
```

Phím tắt: Chuột trái: đánh cờ. Chuột phải / U: hoàn tác. R: ván mới. F: đổi quân đi trước. S: đổi bên bot. B: bật/tắt luật chặn hai đầu. P: bật/tắt nghĩ trước. 1/2/3: độ khó. +/-: đổi kích thước bàn. Esc: thoát.

## Phát triển

Chạy song song hai terminal:

```bash
# Terminal 1: máy chủ Python, tự khởi động lại khi sửa code
.venv\Scripts\python.exe -m server --reload

# Terminal 2: giao diện Vue có hot reload tại http://localhost:5173
cd web
npm run dev
```

Vite chuyển tiếp `/api` và `/ws` sang cổng 8000. Khi sửa xong giao diện, chạy `npm run build` trong `web/` để đóng gói phục vụ qua FastAPI.

### Kiểm thử

Cài đặt thư viện dev:
```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

1. **Self-test của từng engine độc lập:**
```bash
.venv\Scripts\python.exe caro_game.py --self-test        # cờ caro: luật, VCF/VCT, make/unmake
.venv\Scripts\python.exe go_game.py --self-test          # cờ vây: luật, đếm điểm, bot
.venv\Scripts\python.exe xiangqi_game.py --self-test    # cờ tướng: luật, perft, bot
.venv\Scripts\python.exe battleship_game.py --self-test# hải chiến: xếp tàu, bắn chìm, bot
.venv\Scripts\python.exe minesweeper_game.py --self-test # dò mìn: luật, mở lan, chording
.venv\Scripts\python.exe sudoku_game.py --self-test    # sudoku: sinh đề duy nhất, giải, gợi ý
```

2. **Kiểm thử máy chủ với pytest:**
```bash
.venv\Scripts\python.exe -m pytest server                # Chạy toàn bộ test máy chủ

# Hoặc chạy kiểm thử riêng từng trò:
.venv\Scripts\python.exe -m pytest server/tests/test_caro.py
.venv\Scripts\python.exe -m pytest server/tests/test_go.py
.venv\Scripts\python.exe -m pytest server/tests/test_xiangqi.py
.venv\Scripts\python.exe -m pytest server/tests/test_battleship.py
.venv\Scripts\python.exe -m pytest server/tests/test_mines.py
.venv\Scripts\python.exe -m pytest server/tests/test_sudoku.py
.venv\Scripts\python.exe -m pytest server/tests/test_leaderboard.py
```

## Cấu trúc thư mục

```
caro_game.py          Engine cờ caro (luật, bot) + game desktop pygame
go_game.py            Engine cờ vây: luật, đếm điểm, bot Monte Carlo
xiangqi_game.py       Engine cờ tướng: luật, bot alpha-beta
battleship_game.py    Engine hải chiến: xếp tàu, bắn chìm, bot xác suất
minesweeper_game.py   Engine dò mìn: luật, mở lan, chording
sudoku_game.py        Engine sudoku: sinh đề duy nhất, giải, gợi ý
GEMINI.md             Quy tắc và kiến trúc cho agent viết code
server/
  app.py              FastAPI + WebSocket /ws, API hệ thống, phục vụ web/dist
  auth.py             Tài khoản, phiên làm việc, bảng solo_scores, elo (SQLite)
  game.py             Lớp Room cơ sở: ghế, đồng hồ, sẵn sàng, elo, đổi bên
  games.py            Đăng ký GameSpec cho các trò đối kháng
  bot_driver.py       Lớp ThreadedBotDriver điều khiển luồng bot dùng chung
  solo.py             Lớp SoloSession và SoloManager cho các trò một người
  bot.py              Bot cờ caro chạy luồng nền, có nghĩ trước
  go_room.py, go_bot.py                 Phòng chơi và bot cờ vây
  xiangqi_room.py, xiangqi_bot.py       Phòng chơi và bot cờ tướng
  battleship_room.py, battleship_bot.py Phòng chơi và bot hải chiến
  mines.py            Quản lý phiên chơi dò mìn
  sudoku.py           Quản lý phiên chơi sudoku
  tests/              Kiểm thử máy chủ chia theo từng trò (pytest)
web/
  src/game.js         Tài khoản, kết nối WebSocket, trạng thái ứng dụng
  src/games.js        Danh mục trò chơi GAMES và tiêu đề TITLES
  src/room.js         Composable useRoomView dùng chung cho các màn chơi phòng
  src/components/
    HubView.vue       Sảnh chung dạng lưới ô, thanh công cụ, hộp thoại tạo phòng 2 bước
    LeaderboardView.vue Bảng xếp hạng Elo và kỷ lục Dò mìn / Sudoku
    LoginView, AdminView, PasswordView
    GameView / CaroBoard (cờ caro)
    GoGameView / GoBoard (cờ vây)
    XiangqiGameView / XiangqiBoard (cờ tướng)
    BattleshipGameView / BattleshipShip (hải chiến)
    MinesweeperView, SudokuView
    create/           Form tạo phòng từng trò (CreateCaro, CreateGo, CreateXiangqi, CreateBattleship)
    room/             Component thanh bên dùng chung (PlayerList, RequestBox, InviteBox)
    battleship/       Component hải chiến (SeaBoard, PlacementPanel, BattlePanel)
```

Giao thức WebSocket được mô tả chi tiết ở đầu file [server/app.py](server/app.py).

## Bot hoạt động thế nào

- **Cờ caro:** Iterative deepening, alpha-beta/PVS, bảng chuyển vị (transposition table) với mã khóa Zobrist, history heuristic. Tích hợp chuỗi ép thắng VCF (liên tục bốn) và VCT (ba và bốn). Tính năng nghĩ trước (pondering) trong lượt của đối thủ giúp máy phản xạ nhanh.
- **Cờ vây:** Thuật toán Monte Carlo tree search (MCTS) mô phỏng ngẫu nhiên các ván cờ nhanh để đánh giá tỷ lệ chiến thắng và chọn điểm đặt quân tối ưu (đặc biệt hiệu quả trên bàn 9×9).
- **Cờ tướng:** Tìm kiếm alpha-beta kết hợp hàm đánh giá thế cờ dựa trên giá trị quân cờ, vị trí kiểm soát chiến thuật và độ an toàn của Tướng.
- **Hải chiến:** Phân tích bản đồ mật độ xác suất (probability density map) trên các ô chưa bắn dựa trên kích thước các tàu còn sống, kết hợp thuật toán truy kích theo trục khi bắn trúng một phần thân tàu.

## Giới hạn & Lưu ý

- **Nâng cấp dữ liệu:** Ở lần khởi động máy chủ đầu tiên sau khi nâng cấp hệ thống, điểm kỷ lục Dò mìn và Sudoku cũ sẽ tự động được chuyển sang bảng chung `solo_scores` (khuyến nghị sao lưu tệp `data/caro.db` trước khi nâng cấp).
- **Bộ nhớ tiến trình:** Bot của các phòng chơi chung một tiến trình Python; nhiều ván đấu máy cùng lúc có thể làm bot tính toán chậm hơn. Phòng chơi lưu trong bộ nhớ RAM: khởi động lại máy chủ sẽ kết thúc các phòng đang chơi (phòng trống tự xóa sau 10 phút).
- **Bảo mật mạng:** Chưa tích hợp HTTPS và giới hạn số lần thử mật khẩu sai; chỉ nên vận hành máy chủ trong mạng LAN tin cậy, không mở trực tiếp ra Internet mà không có proxy bảo vệ.
