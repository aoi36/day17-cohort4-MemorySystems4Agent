# Phân tích kết quả Benchmark (Bước 8)

## 1. Kết quả Benchmark thực tế

### Standard Benchmark (`data/conversations.json` - 10 hội thoại)

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
|---|---|---|---|---|---|---|
| **Baseline** | 1866 | 15671 | 0.0% | 0.31 | 0 | 0 |
| **Advanced** | 2833 | 28396 | 100.0% | 1.00 | 277 | 0 |

### Long-Context Stress Benchmark (`data/advanced_long_context.json` - hội thoại siêu dài)

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
|---|---|---|---|---|---|---|
| **Baseline** | 308 | 22542 | 0.0% | 0.47 | 0 | 0 |
| **Advanced** | 1119 | 11751 | 100.0% | 1.00 | 219 | 11 |

---

## 2. Vì sao Advanced có recall tốt hơn Baseline

- **Cơ chế Baseline**: Chỉ duy trì bộ nhớ cục bộ trong từng `thread_id` (in-memory state). Khi người dùng mở thread hoặc session mới để hỏi câu hỏi recall, baseline hoàn toàn mất ngữ cảnh cũ, dẫn đến **Cross-session recall = 0.0%**.
- **Cơ chế Advanced**: Tích hợp tầng lưu trữ bền vững `User.md` thông qua [UserProfileStore](src/memory_store.py). Mọi fact ổn định được trích xuất (tên, nơi ở, nghề nghiệp, đồ uống, style câu trả lời) được lưu trực tiếp vào đĩa. Khi sang thread mới, agent nạp lại profile này vào prompt context, giúp đạt **Cross-session recall = 100.0%** và chất lượng phản hồi tối đa (1.00).

---

## 3. Vì sao Advanced có thể tốn hơn ở hội thoại ngắn

- Ở các hội thoại ngắn (như trong Standard Benchmark), số lượng lượt trao đổi chưa đủ dài để vượt qua ngưỡng compact memory (`compact_threshold_tokens = 600`).
- Vì vậy, `AdvancedAgent` phải gánh thêm chi phí cố định (overhead) ở mọi lượt:
  1. Header và nội dung của `User.md`.
  2. Lời nhắc hệ thống (system prompt) định hướng ngữ cảnh.
- Kết quả: `Prompt tokens processed` của Advanced đạt 28,396 tokens, cao hơn so với 15,671 tokens của Baseline. Đây là đánh đổi (trade-off) hợp lý để đổi lấy khả năng recall xuyên suốt các phiên.

---

## 4. Vì sao Compact giúp Advanced có lợi thế ở hội thoại dài

- Trong Long-Context Stress Benchmark, người dùng đưa vào các lượt trao đổi rất dài chứa nhiều tin tức và dữ kiện phức tạp.
- **Baseline** tích lũy toàn bộ tin nhắn thô từ đầu đến cuối theo cấp số cộng, khiến lượng prompt token xử lý phình to lên tới **22,542 tokens**.
- **Advanced** kích hoạt `CompactMemoryManager`: khi lượng token vượt ngưỡng, hệ thống tự động gom các tin nhắn cũ và tóm tắt thành đoạn summary ngắn gọn, chỉ giữ lại một số lượng message gần nhất (`keep_messages = 4`).
- Với **11 lần compactions**, Advanced đã kéo lượng prompt tokens xử lý xuống còn **11,751 tokens** (tiết kiệm gần **48%** chi phí context) mà vẫn đảm bảo độ chính xác và khả năng trả lời đầy đủ.

---

## 5. File memory tăng trưởng ra sao và rủi ro gì đi kèm

- **Mức độ tăng trưởng**:
  - File `User.md` chỉ tăng từ 0 lên khoảng **219 - 277 bytes** sau toàn bộ các lượt test. Nhờ cơ chế chỉ trích xuất các fact cốt lõi có cấu trúc (`- key: value`), kích thước file được kiểm soát rất tốt.
- **Rủi ro đi kèm trong thực tế**:
  1. **Memory Bloat & Noise Accumulation**: Nếu bộ trích xuất không có bộ lọc câu hỏi/câu đùa (false positive updates), file `User.md` sẽ bị phình to bởi các thông tin rác hoặc hiểu nhầm câu hỏi thành fact.
  2. **Stale Information & Conflicts**: Khi người dùng thay đổi thông tin (ví dụ: chuyển từ backend sang MLOps, đổi nơi ở từ Huế sang Đà Nẵng), nếu hệ thống không có cơ chế ghi đè cập nhật (conflict resolution), agent sẽ lưu trữ các thông tin mâu thuẫn nhau.
  3. **Lossy Compression**: Compact memory sử dụng tóm tắt nên có thể vô tình làm mất các tiểu tiết kỹ thuật cụ thể của những lượt trao đổi cũ nếu không được lưu vào persistent memory.
  4. **Privacy / PII Risk**: Lưu trữ trực tiếp thông tin người dùng dạng plain text đòi hỏi phải có cơ chế mã hóa, phân quyền và tuân thủ các quy định bảo mật dữ liệu.
