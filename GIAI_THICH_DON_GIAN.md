# Giải thích đơn giản — Lab 23 LangGraph

## Chúng ta đã xây dựng cái gì?

Hãy tưởng tượng bạn có một **robot trợ lý** ngồi ở quầy lễ tân.
Khi có người đến hỏi, robot sẽ:

1. Nghe câu hỏi
2. Suy nghĩ xem câu hỏi thuộc loại gì
3. Xử lý theo đúng cách
4. Trả lời

---

## Robot làm việc như thế nào?

Giống như một **bản đồ chỉ đường** — robot đi theo từng bước một:

```
Người hỏi → Robot nghe → Robot phân loại → Robot xử lý → Robot trả lời
```

---

## 5 loại câu hỏi robot có thể nhận

| Loại | Ví dụ | Robot làm gì? |
|---|---|---|
| **Đơn giản** | "Đổi mật khẩu thế nào?" | Trả lời ngay |
| **Cần tra cứu** | "Đơn hàng 12345 ở đâu?" | Tra cứu máy tính rồi trả lời |
| **Câu hỏi mơ hồ** | "Sửa nó đi!" | Hỏi lại: "Bạn muốn sửa cái gì?" |
| **Nguy hiểm** | "Xóa tài khoản này!" | Hỏi sếp xem có được phép không |
| **Bị lỗi** | "Hệ thống bị timeout" | Thử lại 3 lần, nếu vẫn lỗi thì báo cáo |

---

## Những file chúng ta đã viết

### 📄 `state.py` — Trí nhớ của robot
> Giống như **tờ giấy ghi chú** mà robot cầm trong tay.
> Robot ghi lên đó: câu hỏi là gì, đã thử bao nhiêu lần, câu trả lời là gì.
> Có những thông tin chỉ được **thêm vào** (không xóa) như nhật ký,
> có những thông tin được **ghi đè** như "đang ở bước nào".

### 📄 `nodes.py` — Các bước làm việc của robot
> Giống như **các công đoạn trong dây chuyền sản xuất**.
> Mỗi node (nút) là một việc robot làm:
> - `intake` = Nghe và dọn dẹp câu hỏi
> - `classify` = Phân loại câu hỏi thuộc nhóm nào
> - `tool` = Tra cứu thông tin từ máy tính
> - `evaluate` = Kiểm tra kết quả tra cứu có tốt không
> - `retry` = Thử lại nếu bị lỗi
> - `dead_letter` = Bỏ cuộc và báo cáo nếu thử quá nhiều lần
> - `answer` = Viết câu trả lời
> - `approval` = Hỏi sếp xem có được phép làm không

### 📄 `routing.py` — Bảng chỉ đường
> Giống như **biển báo giao thông**.
> Sau mỗi bước, robot nhìn vào bảng này để biết đi đường nào tiếp theo.
> Ví dụ: "Nếu tra cứu bị lỗi → thử lại. Nếu tra cứu thành công → trả lời."

### 📄 `graph.py` — Sơ đồ toàn bộ hành trình
> Giống như **bản đồ toàn thành phố**.
> Nối tất cả các bước lại với nhau, xác định đường đi từ đầu đến cuối.

### 📄 `metrics.py` — Bảng điểm
> Giống như **phiếu báo điểm**.
> Sau khi robot làm xong tất cả bài test, file này tính:
> - Làm đúng bao nhiêu bài? (success_rate)
> - Trung bình đi qua bao nhiêu bước? (avg_nodes_visited)
> - Tổng số lần phải thử lại? (total_retries)

### 📄 `report.py` — Bản báo cáo
> Giống như **bài tập làm văn tổng kết**.
> Tự động viết một bản báo cáo đầy đủ dựa trên điểm số.

### 📄 `extension_demo.py` — Bài tập thêm (nâng cao)
> Robot còn học thêm 3 kỹ năng đặc biệt:
> 1. **Lưu vào ổ cứng** — Tắt máy bật lại vẫn nhớ đang làm gì
> 2. **Tiếp tục sau khi bị ngắt** — Như đọc sách bị gián đoạn, mở ra đọc tiếp từ trang đánh dấu
> 3. **Quay về quá khứ** — Xem lại từng bước đã làm, có thể chạy lại từ bất kỳ bước nào

---

## Kết quả cuối cùng

| Bài test | Kết quả |
|---|---|
| 7 bài kiểm tra | ✅ Tất cả đúng (100%) |
| Kiểm tra code sạch | ✅ Không có lỗi |
| Báo cáo | ✅ Đã viết xong |
| Bài nâng cao | ✅ Làm thêm 3 bài |

---

## Tóm lại bằng 1 câu

> Chúng ta đã xây dựng một robot trợ lý thông minh, biết phân loại câu hỏi,
> tự thử lại khi bị lỗi, hỏi xin phép trước khi làm việc nguy hiểm,
> và còn nhớ được lịch sử làm việc dù tắt máy bật lại.

---

## 7 bài test của robot (`scenarios.jsonl`)

Đây là **7 bài kiểm tra** để xem robot có phân loại đúng không.
Mỗi bài có một câu hỏi và một đáp án đúng (`expected_route`).

### S01 — Câu hỏi đơn giản
- **Câu hỏi:** "How do I reset my password?"
- **Robot phải làm:** Trả lời ngay, không cần tra cứu hay xin phép.
- **Đáp án đúng:** `simple`

### S02 — Cần tra cứu dữ liệu
- **Câu hỏi:** "Please lookup order status for order 12345"
- **Robot phải làm:** Gọi tool tra cứu hệ thống rồi mới trả lời.
- **Đáp án đúng:** `tool`

### S03 — Câu hỏi mơ hồ
- **Câu hỏi:** "Can you fix it?"
- **Robot phải làm:** "Nó" là cái gì? Không đoán được → hỏi lại cho rõ.
- **Đáp án đúng:** `missing_info`

### S04 — Hành động nguy hiểm
- **Câu hỏi:** "Refund this customer and send confirmation email"
- **Robot phải làm:** Hoàn tiền + gửi email là việc ảnh hưởng thật → phải xin phép sếp trước.
- **Đáp án đúng:** `risky` | `requires_approval: true`
- **Keyword nhận ra:** `refund`, `send`

### S05 — Bị lỗi, cần thử lại
- **Câu hỏi:** "Timeout failure while processing request"
- **Robot phải làm:** Hệ thống báo lỗi → thử lại tối đa 3 lần, lần 3 thành công.
- **Đáp án đúng:** `error` | `should_retry: true`
- **Keyword nhận ra:** `timeout`, `failure`

### S06 — Hành động phá hủy
- **Câu hỏi:** "Delete customer account after support verification"
- **Robot phải làm:** Xóa tài khoản là không thể hoàn tác → phải xin phép sếp.
- **Đáp án đúng:** `risky` | `requires_approval: true`
- **Keyword nhận ra:** `delete`

### S07 — Thất bại hoàn toàn (dead letter)
- **Câu hỏi:** "System failure cannot recover after multiple attempts"
- **Robot phải làm:** `max_attempts=1` → chỉ được thử 1 lần. Vẫn lỗi → bỏ cuộc, ghi vào danh sách chờ người thật xử lý.
- **Đáp án đúng:** `error` → `dead_letter`

---

### S08 — Xung đột ưu tiên (Priority Conflict)
- **Câu hỏi:** "Cancel the order 12345 immediately"
- **Cái bẫy:** Câu này có cả từ `cancel` (nguy hiểm) lẫn `order` (tra cứu). Robot chọn cái nào?
- **Robot phải làm:** `cancel` được kiểm tra **trước** → robot chọn `risky`, xin phép sếp.
- **Bài học:** Thứ tự ưu tiên: Nguy hiểm > Lỗi > Tra cứu > Mơ hồ > Đơn giản

### S09 — Vòng lặp thử lại vừa đủ (max_attempts=2)
- **Câu hỏi:** "Error processing transaction please retry"
- **Cái bẫy:** `max_attempts=2` (không phải 1 hay 3). Robot thử đúng 2 lần rồi vào dead_letter.
- **Robot phải làm:** Lần thử 1 → lỗi → retry. Lần thử 2 → lỗi → `attempt=2 >= max_attempts=2` → dead_letter.
- **Bài học:** Giới hạn thử lại hoạt động chính xác với bất kỳ số nào.

### S10 — Có thông tin cá nhân (PII)
- **Câu hỏi:** "My account email user@example.com needs password reset"
- **Cái bẫy:** Câu hỏi có địa chỉ email thật → robot phải xóa đi trước khi xử lý.
- **Robot phải làm:** `intake_node` đổi email thành `[EMAIL]`, không có keyword nguy hiểm → route `simple`.
- **Bài học:** Robot tự bảo vệ thông tin cá nhân, rồi mới phân loại.

### S11 — Câu cực ngắn và mơ hồ
- **Câu hỏi:** "What about that?"
- **Cái bẫy:** Chỉ có 3 từ, không có từ `it` (keyword cũ), nhưng có từ `that`.
- **Robot phải làm:** 3 từ < 5 từ + có `that` → `missing_info` → hỏi lại.
- **Bài học:** Robot nhận ra câu quá mơ hồ dù không đúng keyword mẫu.

### S12 — Chuyển tiền (nguy hiểm tài chính)
- **Câu hỏi:** "Transfer all funds from account 111 to account 222"
- **Cái bẫy:** Câu này có số tài khoản cụ thể, trông giống tra cứu nhưng thực ra là lệnh tài chính.
- **Robot phải làm:** Từ `transfer` → `risky` → xin phép sếp trước khi thực hiện.
- **Bài học:** Keyword `transfer` đủ để kích hoạt bảo vệ, dù câu hỏi trông "vô hại".

---

### Bảng tóm tắt 12 bài test

| ID | Câu hỏi tóm tắt | Robot làm gì | Điểm khó |
|---|---|---|---|
| S01 | Đổi mật khẩu | Trả lời thẳng | — |
| S02 | Tra đơn hàng | Gọi tool | — |
| S03 | "Fix it?" | Hỏi lại | Thiếu thông tin |
| S04 | Hoàn tiền | Xin phép sếp | `requires_approval` |
| S05 | Timeout | Thử lại ≤3 lần | `should_retry` |
| S06 | Xóa tài khoản | Xin phép sếp | `destructive` |
| S07 | Lỗi hệ thống | Thử 1 lần → bỏ | `max_attempts=1` |
| **S08** | **Cancel đơn hàng** | **Xin phép (không tra cứu)** | **Xung đột keyword** |
| **S09** | **Lỗi giao dịch** | **Thử 2 lần → bỏ** | **max_attempts=2** |
| **S10** | **Email + đổi mật khẩu** | **Xóa PII rồi trả lời** | **Có thông tin cá nhân** |
| **S11** | **"What about that?"** | **Hỏi lại** | **Câu cực ngắn** |
| **S12** | **Chuyển tiền** | **Xin phép sếp** | **Rủi ro tài chính** |

---

### Ý nghĩa từng trường trong file

| Trường | Nghĩa là gì |
|---|---|
| `id` | Tên bài test |
| `query` | Câu hỏi của khách |
| `expected_route` | Đáp án đúng — robot phải phân loại vào đây |
| `requires_approval` | Có cần hỏi sếp không? |
| `should_retry` | Có khả năng bị lỗi tạm thời không? |
| `max_attempts` | Được thử tối đa bao nhiêu lần (mặc định 3) |
| `tags` | Nhãn phân nhóm để dễ tìm khi debug |
