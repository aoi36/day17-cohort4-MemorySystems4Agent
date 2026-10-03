# Student Implementation & Benchmark Analysis

This `src/` folder contains the implementation of the memory systems for Day 17.

- High-level architecture: Short-term memory (in-thread), Persistent memory (`User.md`), and Compact memory.
- Benchmark suites: Standard benchmark (`data/conversations.json`) + Long-Context Stress benchmark (`data/advanced_long_context.json`).
- Supported providers: `openai`, `custom`, `gemini`, `anthropic`, `ollama`, `openrouter`.

## Phân tích kết quả Benchmark

1. **Vì sao Advanced có recall tốt hơn Baseline:**
   - `BaselineAgent` chỉ lưu trữ tin nhắn trong cùng một thread và hoàn toàn không có persistent storage. Khi sang thread mới, toàn bộ ngữ cảnh trước đó bị mất (recall đạt 0%).
   - `AdvancedAgent` tích hợp `UserProfileStore` ghi nhận các fact ổn định (tên, nơi ở, nghề nghiệp, đồ uống, style) vào file `User.md`. Khi mở session mới, thông tin này được nạp lại vào prompt context giúp đạt tỷ lệ recall 100%.

2. **Vì sao Advanced có thể tốn hơn ở hội thoại ngắn:**
   - Ở các hội thoại ngắn, overhead nạp toàn bộ profile `User.md` và tóm tắt vào mỗi lượt khiến tổng prompt tokens của `Advanced` cao hơn `Baseline` (ví dụ ở Standard Benchmark: 28,376 vs 15,671 prompt tokens).

3. **Vì sao Compact giúp Advanced có lợi thế vượt trội ở hội thoại dài:**
   - Trong Long-Context Stress Benchmark, `BaselineAgent` kéo theo toàn bộ lịch sử thô qua từng lượt, khiến prompt token tăng tuyến tính theo cấp số cộng (đạt 22,542 tokens).
   - `AdvancedAgent` kích hoạt `CompactMemoryManager` nén các message cũ thành summary ngắn gọn khi vượt ngưỡng token (kích hoạt 11 lần compaction). Kết quả là prompt tokens giảm gần 50% (còn 11,664 tokens) mà vẫn giữ được chất lượng phản hồi và recall.

4. **Tăng trưởng file memory và rủi ro đi kèm:**
   - `User.md` tăng dần khi có thông tin mới (~200 - 300 bytes cho một user).
   - Rủi ro: file memory có thể phình to không giới hạn nếu lưu cả chi tiết tạm thời hoặc lưu sai khi người dùng chỉ đặt câu hỏi/nói đùa. Hệ thống đã xử lý bằng cách lọc query turns và hỗ trợ conflict handling (đè fact mới khi có đính chính).

