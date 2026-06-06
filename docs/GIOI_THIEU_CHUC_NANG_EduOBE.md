# EduOBE — Phần mềm Quản lý Đào tạo theo Chuẩn đầu ra (OBE) & Kiểm định AUN-QA
## Bản mô tả chức năng & Giới thiệu cho các trường đại học

> **Số hóa toàn bộ chuỗi học thuật — từ Đề án mở ngành đến từng Đề thi — trên một nền tảng duy nhất, có Trí tuệ Nhân tạo (AI) vừa TẠO nội dung, vừa THẨM ĐỊNH & NÂNG CẤP chất lượng ở mọi khâu, với truy vết chuẩn đầu ra xuyên suốt.**

---

## 1. Bối cảnh & vì sao trường cần EduOBE

Chuyển đổi sang **đào tạo theo chuẩn đầu ra (Outcome-Based Education)** và chuẩn bị **kiểm định AUN-QA / Bộ GD&ĐT** là yêu cầu bắt buộc với các trường đại học. Tuy nhiên, cách làm thủ công hiện nay khiến công việc nặng nề, rời rạc và rủi ro.

### Những "nỗi đau" quen thuộc

| Nỗi đau | Hậu quả |
|---|---|
| Đề cương, ma trận, đề thi nằm rải rác trong hàng nghìn file Word/Excel của từng giảng viên | Lạc phiên bản, thất lạc minh chứng, mỗi người một mẫu, không kiểm soát được |
| Mất **tính nhất quán dọc** (constructive alignment): CLO không gắn PLO, đánh giá không phủ hết CLO | Bị đoàn kiểm định "bắt lỗi", phải làm lại từ đầu |
| Soạn đề cương, giáo trình, ngân hàng câu hỏi, ma trận đề thi **thủ công** | Tốn hàng trăm giờ công mỗi học kỳ; chất lượng không đồng đều giữa các giảng viên |
| Bóc tách PLO/PI/học phần từ đề án mở ngành dày hàng trăm trang **bằng tay** | Chậm, sai sót, khó đối chiếu |
| Đến kỳ kiểm định mới **cuống cuồng gom minh chứng** | Áp lực dồn cục, báo cáo phủ chuẩn không kịp, thiếu dữ liệu |
| Không có ai **rà soát chất lượng học thuật** từng CLO/từng câu hỏi một cách nhất quán | Mất điểm ở tiêu chí cốt lõi của AUN-QA |
| Không trả lời nhanh được: *"PLO này đo bằng câu hỏi nào, ở học phần nào?"* | Lúng túng trước đoàn đánh giá |

### EduOBE giải quyết tận gốc

Đưa **toàn bộ quy trình lên một nền tảng web duy nhất**, bảo đảm **truy vết hai chiều xuyên suốt**, dùng **AI tự động hóa và kiểm soát chất lượng** — đồng thời **luôn để con người quyết định cuối cùng** (human-in-the-loop).

---

## 2. Chuỗi giá trị "một mạch"

```
   Đề án mở ngành (PDF/DOCX, kể cả bản scan)
        │  ✨ AI bóc tách tự động
        ▼
   CTĐT → PLO → PI → Danh mục học phần
        │  ✨ AI soạn đề cương theo chuẩn AUN-QA
        ▼
   Đề cương → CLO → Ma trận CLO×PLO → Đánh giá (kèm Rubric) → Kế hoạch dạy
        │  ✨ AI biên soạn giáo trình & bài giảng
        ▼
   Giáo trình (chương gắn CLO) · Bài giảng + slide
        │  ✨ AI sinh ngân hàng câu hỏi (kèm giải thích/nguồn/rubric)
        ▼
   Ngân hàng câu hỏi → Ma trận đề thi → Đề thi (nhiều mã đề + bảng đặc tả)
        │
        ▼
   Kho minh chứng & Báo cáo phủ chuẩn AUN-QA
```

> **Khác biệt cốt lõi:** mọi mắt xích **ràng buộc dữ liệu với nhau**. Hỏi *"PLO2 đo bằng câu hỏi nào?"* — hệ thống trả lời trong vài giây, không cần lục file.

---

## 3. Các phân hệ chức năng

### 3.1. Trích xuất Đề án mở ngành bằng AI
Tải lên PDF/DOCX (kể cả **bản scan** nhờ OCR tiếng Việt, đọc cả bảng biểu). AI bóc tách có cấu trúc: **ngành, PLO, PI, danh mục học phần, ma trận học phần–PLO** → con người rà soát & xác nhận.

### 3.2. CTĐT & Chuẩn đầu ra
CRUD Chương trình / PLO / PI / Học phần; **ma trận Học phần × PLO (I/R/M)**; **kiểm tra độ phủ** (cảnh báo PLO chưa được học phần nào đạt mức Master); **AI chuẩn hóa PLO**; **xóa/dọn** chương trình.

### 3.3. Đề cương học phần (chuẩn AUN-QA)
- **AI soạn đề cương**: CLO song ngữ Việt–Anh, ma trận CLO×PLO, cấu phần đánh giá **kèm rubric**, kế hoạch dạy.
- **Import đề cương đã có** vào đúng học phần: AI bóc tách → rà soát/sửa ánh xạ CLO–PLO → lưu.
- **AI kiểm tra chất lượng** (chấm điểm + lỗ hổng) và **AI nâng cấp** → phiên bản mới (giữ bản gốc để đối chiếu).
- Kiểm tra **alignment** bắt buộc trước khi duyệt; vòng đời trạng thái; so sánh phiên bản; **xuất DOCX**.
- **Bảng "sức khỏe đề cương toàn ngành"**: điểm chất lượng AI từng học phần — nhìn toàn cảnh trước kiểm định.

### 3.4. Giáo trình
**AI tạo cả giáo trình / từng chương** (chương sâu 25–40 trang); **AI đánh giá + nâng cấp** chương; xuất **DOCX & PDF**. Tác vụ nặng chạy **nền có thanh tiến độ**.

### 3.5. Bài giảng
**AI soạn bài giảng theo buổi** bám giáo trình + CLO; **AI đánh giá + nâng cấp** (nội dung + slide); xuất **DOCX & PPTX**.

### 3.6. Ngân hàng câu hỏi
**AI sinh câu hỏi** bám giáo trình theo CLO, **kèm giải thích đáp án, nguồn, và rubric** cho tự luận/bài tập; quy trình **thẩm định 5 trạng thái** + duyệt hàng loạt; **AI đánh giá + nâng cấp**; import/export **CSV & Excel**; dashboard độ phủ.

### 3.7. Ma trận đề thi & Tạo đề
**AI tạo/tối ưu ma trận** (CLO×Bloom×độ khó), **cân điểm chính xác** về thang điểm, **gắn cấu phần đánh giá** của đề cương; **AI đánh giá theo AUN-QA + nâng cấp**. Sinh đề **chỉ từ câu đã duyệt**, **nhiều mã đề**, **bảng đặc tả + mapping CLO–PLO/PI**, xuất DOCX.

### 3.8. Kiểm định & Đảm bảo chất lượng
**Báo cáo phủ chuẩn PLO→PI→CLO→đánh giá**; kho minh chứng; **audit log**; **đóng gói minh chứng (zip)** cho đoàn đánh giá.

### 3.9. Quản trị & vận hành
Phân quyền **RBAC theo vai trò & phạm vi**; Admin quản lý **API key AI** dùng chung (Claude/OpenAI); **trang theo dõi chi phí AI** (token/chi phí theo chương trình) + hạn mức; versioning; soft-delete; song ngữ Việt/Anh.

---

## 4. Điểm khác biệt: AI vừa TẠO, vừa THẨM ĐỊNH & NÂNG CẤP

Khác với công cụ chỉ "sinh nội dung", EduOBE tích hợp **trợ lý kiểm định AI ở MỌI khâu**: chấm điểm /100, chỉ ra lỗi/cảnh báo theo tiêu chí AUN-QA, và **nâng cấp tự động** theo góp ý.

| Đối tượng | Đánh giá bằng AI | Nâng cấp bằng AI |
|---|---|---|
| Đề cương | Chất lượng CLO / alignment / đánh giá | Soạn lại → phiên bản mới (giữ bản gốc) |
| Ngân hàng câu hỏi | Chấm từng câu (Bloom, đáp án, nhiễu, rubric, độ phủ) | Viết lại câu chưa duyệt |
| Ma trận đề thi | Theo AUN-QA (tổng điểm, phủ CLO, cân Bloom) | Tối ưu bám điểm yếu |
| Giáo trình (chương) | Phủ CLO, chiều sâu, cấu trúc, ví dụ | Viết lại nội dung |
| Bài giảng | Mục tiêu/cấu trúc sư phạm/slide | Viết lại nội dung + slide |

> Đây là tính năng **biến mỗi giảng viên thành một chuyên gia thiết kế OBE** — chất lượng đồng đều toàn trường, giảm phụ thuộc vào số ít cán bộ ĐBCL giàu kinh nghiệm.

---

## 5. Giá trị mang lại (định lượng)

| Hạng mục | Trước EduOBE | Với EduOBE |
|---|---|---|
| Soạn 1 đề cương đạt chuẩn AUN-QA | 8–16 giờ/giảng viên | **30–60 phút** |
| Dựng 1 ngân hàng câu hỏi cho học phần | 2–4 ngày | **Vài giờ** |
| Lập 1 ma trận đề thi cân chuẩn | 3–6 giờ | **Vài phút** |
| Gom minh chứng phủ chuẩn cho 1 ngành | Hàng tuần, cuống cuồng | **Tức thời, sẵn sàng quanh năm** |
| Rà soát chất lượng học thuật | Phụ thuộc vài chuyên gia | **AI rà toàn bộ, nhất quán** |

**Giá trị tổng thể:**
- **Tiết kiệm hàng nghìn giờ công** mỗi năm; giảng viên tập trung vào chuyên môn thay vì định dạng tài liệu.
- **Giảm rủi ro trượt tiêu chí kiểm định** — đồng nghĩa giảm chi phí làm lại và bảo vệ uy tín nhà trường.
- **Chuẩn hóa chất lượng** trên toàn trường; số hóa & lưu vết đầy đủ phục vụ AUN-QA/MOET.
- **Sẵn sàng kiểm định mọi lúc**: báo cáo phủ chuẩn và gói minh chứng chỉ một cú nhấp.

---

## 6. Quy mô & độ tin cậy (sẵn sàng triển khai toàn trường)

- Thiết kế cho **hàng chục chương trình, hàng nghìn học phần, hàng trăm nghìn câu hỏi**: cơ sở dữ liệu được **đánh chỉ mục (index)**, **phân trang**, **pool kết nối** tối ưu.
- **Lưu trữ file bền vững trên đám mây (GCS)**, **tác vụ AI nặng chạy nền có tiến độ**, **kiểm soát chi phí/giới hạn tốc độ AI** kèm **hạn mức token theo chương trình**.
- **Bảo mật**: phân quyền theo vai trò & phạm vi, nhật ký kiểm toán (audit log), không xóa cứng dữ liệu đã ban hành.
- **Human-in-the-loop**: AI hỗ trợ, con người duyệt cuối — dữ liệu học thuật luôn thuộc về nhà trường.

---

## 7. Đối tượng phù hợp

Trường/khoa đang **chuyển đổi sang OBE** hoặc **chuẩn bị kiểm định AUN-QA / Bộ GD&ĐT**; phòng **Đảm bảo chất lượng**, phòng **Đào tạo**, và **đội ngũ giảng viên** muốn chuẩn hóa và tăng tốc quy trình.

---

## 8. Kêu gọi hành động

> **Đăng ký demo 60 phút + gói thí điểm 1 khoa**: tải một đề án mở ngành lên, để AI dựng PLO/PI/học phần, soạn một đề cương đạt chuẩn — rồi để AI **chấm điểm và tự nâng cấp** ngay trước mắt bạn.

**EduOBE — Đào tạo theo chuẩn đầu ra, kiểm định trong tầm tay.**

*Liên hệ: [tên đầu mối] · [email] · [điện thoại] · [website]*
