---
name: caro-engine
description: Quy tắc khi sửa engine cờ caro trong caro_game.py (Position, bảng mẫu dòng cơ số 3, CaroBot, VCF/VCT, nghĩ trước, mức độ khó). Dùng trước khi thay đổi thuật toán bot, hàm đánh giá, luật chặn hai đầu, hoặc khi bot đánh sai hay chậm.
---

# Engine cờ caro: bất biến cần giữ

Engine dùng chung cho game desktop (`CaroGame`) và máy chủ web (`server/bot.py`).
Mọi thay đổi phải giữ cho cả hai chạy được.

## Các bất biến
1. **Một bộ luật.** `winning_line` (2D, giao diện/server) và `Position.wins` /
   `winning_moves` (bot) phải luôn cho cùng kết quả ở cả `strict=False` và `strict=True`.
   Test `test_virtual_win_matches_shared_rules` kiểm tra điều này.
2. **Bảng mẫu dòng.** Mỗi dòng là một số cơ số 3 (`Position.codes`); ô đầu dòng là chữ số thấp nhất.
   Đánh quân thì cộng `player * 3**vị_trí`. Đặc trưng của dòng được tra trong `_LINE_TABLES`, tính lười bằng
   `line_features`. Khi đổi `line_features`, bảng tự đúng theo (bảng chỉ là cache trong tiến trình).
   `play`/`undo` phải khôi phục đủ `codes`, `line_scores`, `line_wins`, `win_counts`, `win_points`, `hash`.
3. **Chứng minh thắng phải chính xác.** `self.proofs[(hash, bên đi)] = (nước, số nước)` được
   `_search` dùng như kết quả thắng chắc. Chỉ ghi vào đó khi mọi nước đáp hợp lệ của đối thủ
   đã được xét:
   - VCF: mọi nước trong `defensive_moves` + kiểm tra đối thủ thắng ngay.
   - VCT (`_vct_defend`): các nước vô hiệu hóa mọi ô đòn kép (`_fork_blocks`, dựa trên
     `Position.threat_cells`) cộng mọi nước tạo bốn phản công. Nước khác thua vì đối thủ
     không có ô thắng. Muốn thêm loại đe dọa mới thì phải giữ được lập luận này.
   - Ở lượt tấn công (OR) được cắt nhánh tùy ý (`VCT_BRANCH`). Ở lượt phòng thủ (AND) **không bao giờ** được cắt.
4. **Thời gian.** Mọi vòng lặp dài gọi `_check()` (hạn `self.clock.deadline` + cancel) hoặc
   `_vcf_check()` (thêm `phase_deadline`). `Clock` dùng chung với luồng giao diện: khi đoán trúng
   nước, hạn chót được rút ngắn từ bên ngoài.
5. **Bộ nhớ đệm giữ qua nhiều nước** (tt, proofs, vcf/vct cache): khóa theo hash nên vẫn hợp lệ.
   Chỉ xóa khi đổi kích thước bàn, WIN_LENGTH hoặc luật (`_prepare`).
6. **Nghĩ trước:** `predict` (đoán nước người) + `choose(..., clock=Clock(inf))`. Desktop
   (`CaroGame.update_bot`) và web (`BotDriver.sync`) cùng xử lý trường hợp đoán trúng/đoán sai
   theo `BotJob`. Sửa một bên thì kiểm tra bên còn lại.

## Kiểm tra sau khi sửa
- `.venv\Scripts\python.exe caro_game.py --self-test` (gồm kiểm chứng VCT thử mọi nước đáp bằng luật 2D).
- `.venv\Scripts\python.exe -m pytest server`.
- Đo tốc độ: gọi `CaroBot(depth, time_budget, move_limit).choose(board, O)` trên một thế giữa ván,
  xem `depth`, `nodes`, `elapsed`. Mốc hiện tại khoảng 8.000 nút/giây; mức Chuyên gia đạt độ sâu 8.
  Dùng `cProfile` để tìm chỗ chậm trước khi tối ưu.
- Với lỗi chiến thuật: dựng thế cờ nhỏ (9×9 hoặc 11×11) thành test trong `self_test`,
  chạy cả hai luật.
