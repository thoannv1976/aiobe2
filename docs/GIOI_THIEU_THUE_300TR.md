# EduOBE — Nền tảng Quản lý Đào tạo theo Chuẩn đầu ra (OBE) & Kiểm định AUN-QA
## Bản giới thiệu — Gói thuê trọn gói **300 triệu đồng/năm**

> **Số hóa toàn bộ chuỗi học thuật — từ Đề án mở ngành đến từng Đề thi — trên một nền tảng duy nhất, có Trí tuệ Nhân tạo (AI) vừa *tạo nội dung* vừa *thẩm định & nâng cấp chất lượng* ở mọi khâu, và truy vết chuẩn đầu ra xuyên suốt.**

---

## 1. Tóm tắt cho lãnh đạo (Executive Summary)

EduOBE là **hệ thống quản trị học thuật chuyên biệt cho OBE/AUN-QA**, giúp một trường đại học:

- **Chuẩn hóa và số hóa** toàn bộ quy trình: CTĐT → PLO/PI → Đề cương/CLO → Giáo trình → Bài giảng → Ngân hàng câu hỏi → Ma trận đề thi → Đề thi → Minh chứng kiểm định.
- **Tự động hóa các công việc nặng nhọc nhất** bằng AI — không chỉ *sinh ra* tài liệu, mà còn **chấm điểm chất lượng theo AUN-QA và tự nâng cấp** theo góp ý.
- **Sẵn sàng kiểm định mọi lúc**: trả lời trong vài giây câu hỏi *"PLO này được đo bằng câu hỏi nào, ở học phần nào?"* và xuất gói minh chứng tự động.

**Giá trị tài chính:** với gói **300 triệu đồng/năm trọn gói toàn trường**, EduOBE thay thế hàng nghìn giờ công soạn thảo thủ công và rủi ro trượt tiêu chí kiểm định — chi phí chỉ tương đương **dưới 2–3 nhân sự bán thời gian**, nhưng phục vụ **không giới hạn giảng viên** trong toàn trường.

---

## 2. Vì sao các trường cần EduOBE?

Chuyển đổi sang đào tạo theo chuẩn đầu ra (Outcome-Based Education) và chuẩn bị kiểm định **AUN-QA / Bộ GD&ĐT** đang là áp lực lớn. Thực tế tại hầu hết các trường:

| 😣 Nỗi đau quen thuộc | Hậu quả |
|---|---|
| Đề cương, ma trận, đề thi nằm rải rác trong hàng nghìn file Word/Excel | Không kiểm soát phiên bản, thất lạc minh chứng, mỗi người một mẫu |
| Mất **tính nhất quán dọc** (constructive alignment): CLO không gắn PLO, đánh giá không phủ hết CLO | Bị đoàn kiểm định "bắt lỗi", phải làm lại từ đầu |
| Soạn đề cương, giáo trình, ngân hàng câu hỏi, ma trận đề thi **thủ công** | Tốn hàng trăm giờ công mỗi kỳ; chất lượng không đồng đều |
| Trích xuất PLO/PI/học phần từ đề án mở ngành dày hàng trăm trang **bằng tay** | Sai sót, chậm, khó đối chiếu |
| Đến kỳ kiểm định mới **cuống cuồng gom minh chứng** | Áp lực dồn cục, báo cáo phủ chuẩn không kịp |
| Không có ai **rà soát chất lượng học thuật** từng CLO, từng câu hỏi một cách nhất quán | Mất điểm ở tiêu chí cốt lõi của AUN-QA |

**EduOBE giải quyết tận gốc:** đưa toàn bộ quy trình lên một nền tảng web duy nhất, **đảm bảo truy vết hai chiều xuyên suốt**, **dùng AI tự động hóa và kiểm soát chất lượng** — đồng thời **luôn giữ con người là người quyết định cuối cùng** (human-in-the-loop).

---

## 3. Chuỗi giá trị "một mạch" — từ trên xuống dưới

```
   Đề án mở ngành (PDF/DOCX, kể cả bản scan)
        │  ✨ AI trích xuất tự động
        ▼
   Chương trình đào tạo → PLO → PI → Danh mục học phần
        │  ✨ AI soạn đề cương theo chuẩn AUN-QA
        ▼
   Đề cương học phần → CLO → Ma trận CLO×PLO → Đánh giá (kèm Rubric) → Kế hoạch dạy
        │  ✨ AI biên soạn giáo trình
        ▼
   Giáo trình theo chương (gắn CLO)
        │  ✨ AI soạn bài giảng + slide
        ▼
   Bài giảng theo buổi (DOCX + PPTX)
        │  ✨ AI sinh ngân hàng câu hỏi (kèm giải thích, nguồn, rubric)
        ▼
   Ngân hàng câu hỏi (CLO + Bloom + độ khó) → Ma trận đề thi
        │  Tự động bốc đề, nhiều mã đề
        ▼
   Đề thi + Đáp án + Bảng đặc tả (mapping CLO–PLO/PI)
        │
        ▼
   Kho minh chứng & Báo cáo phủ chuẩn AUN-QA
```

> **Điểm khác biệt cốt lõi:** mọi mắt xích đều **ràng buộc dữ liệu với nhau**. Hỏi *"PLO2 được đo bằng câu hỏi nào, ở học phần nào?"* — hệ thống trả lời tức thì, không cần lục file.

---

## 4. Các phân hệ chính

### 🤖 4.1. Trích xuất Đề án mở ngành bằng AI
Tải lên đề án/CTĐT (**PDF, DOCX**, kể cả **file scan** nhờ OCR tiếng Việt). AI tự động trích xuất có cấu trúc: **ngành, PLO, PI, danh mục học phần, ma trận học phần–PLO** — kể cả dữ liệu trong **bảng biểu**. Con người rà soát và xác nhận trước khi ghi vào hệ thống.

### 🎯 4.2. Quản lý CTĐT, Chuẩn đầu ra & Độ phủ
CRUD Chương trình/PLO/PI/Học phần; **ma trận Học phần×PLO (I/R/M)**; **kiểm tra độ phủ** — cảnh báo ngay PLO nào chưa được học phần nào đạt mức *Master*.

### 📋 4.3. Đề cương học phần (chuẩn AUN-QA)
AI soạn đề cương bám PLO + mẫu của trường + chuẩn AUN-QA: **CLO song ngữ Việt–Anh**, ma trận CLO×PLO, cấu phần đánh giá **kèm rubric**, kế hoạch giảng dạy. Kiểm tra **alignment** bắt buộc đạt trước khi duyệt; có **vòng đời trạng thái, phiên bản, so sánh khác biệt (diff)** và **xuất DOCX**.

### 📚 4.4. Giáo trình
AI biên soạn **cả giáo trình hoặc từng chương** (chương sâu 25–40 trang), gắn CLO; **xuất DOCX & PDF** (hỗ trợ tiếng Việt đầy đủ).

### 🎓 4.5. Bài giảng
AI soạn **bài giảng theo buổi** bám giáo trình + CLO; **xuất DOCX và slide PPTX**.

### 🏦 4.6. Ngân hàng câu hỏi
AI sinh câu hỏi **bám sát nội dung giáo trình** theo từng CLO, **kèm giải thích đáp án, nguồn (chương/bài giảng), và rubric chấm cho câu tự luận/bài tập**. Quy trình **thẩm định 5 trạng thái**, duyệt hàng loạt, **import/export CSV & Excel**, bảng thống kê độ phủ.

### 🧮 4.7. Ma trận đề thi & Sinh đề
AI thiết kế ma trận (CLO × Bloom × độ khó) **bám ngân hàng hiện có** và **gắn đúng cấu phần đánh giá cuối kỳ của đề cương**; cân điểm chính xác về thang điểm. Tự động **bốc đề nhiều mã đề**, kèm **bảng đặc tả + mapping CLO–PLO/PI**; xuất DOCX.

### 🛡️ 4.8. Kiểm định & Đảm bảo chất lượng
**Báo cáo phủ chuẩn PLO→PI→CLO→đánh giá**, kho minh chứng, **audit log** cho mọi thao tác quan trọng, và **đóng gói minh chứng (zip)** phục vụ đoàn đánh giá.

---

## 5. ⭐ Điểm khác biệt nổi bật: AI **vừa tạo, vừa thẩm định & nâng cấp**

Khác với các công cụ chỉ "sinh nội dung", EduOBE tích hợp **một trợ lý kiểm định AI (QA Reviewer)** ở **mọi khâu**. Với mỗi sản phẩm, hệ thống **chấm điểm /100, chỉ ra lỗi/cảnh báo theo tiêu chí AUN-QA, và nâng cấp tự động** theo góp ý — giữ nguyên bản gốc để đối chiếu:

| Đối tượng | Đánh giá bằng AI | Nâng cấp bằng AI |
|---|---|---|
| **Đề cương** | Chấm chất lượng CLO/alignment/đánh giá | Soạn lại → **phiên bản mới**, giữ bản gốc để diff |
| **Ngân hàng câu hỏi** | Chấm từng câu (Bloom, đáp án, nhiễu, rubric, độ phủ) | Viết lại câu chưa duyệt; **không đụng câu đã duyệt** |
| **Ma trận đề thi** | Đánh giá theo AUN-QA (tổng điểm, phủ CLO, cân Bloom) | Tối ưu bám đúng điểm yếu đã chỉ ra |
| **Giáo trình (chương)** | Chấm độ phủ CLO, chiều sâu, cấu trúc, ví dụ | Viết lại nội dung chương khắc phục |
| **Bài giảng** | Chấm mục tiêu/cấu trúc sư phạm/slide | Viết lại nội dung + cập nhật slide |

> Đây là tính năng **biến mỗi giảng viên thành một chuyên gia thiết kế OBE** — chất lượng đồng đều toàn trường, giảm phụ thuộc vào số ít cán bộ ĐBCL giàu kinh nghiệm.

**Linh hoạt mô hình AI:** quản trị viên cấu hình **API key của Claude (Anthropic) hoặc OpenAI** dùng chung toàn trường. Mọi kết quả AI đều được **kiểm tra định dạng chặt chẽ** và **do con người duyệt cuối**.

---

## 6. Lợi ích định lượng — Vì sao 300 triệu/năm là *đầu tư có lãi*

| Hạng mục | Trước EduOBE | Với EduOBE |
|---|---|---|
| Soạn 1 đề cương đạt chuẩn AUN-QA | 8–16 giờ/giảng viên | **30–60 phút** (AI soạn + rà soát) |
| Dựng 1 ngân hàng câu hỏi cho học phần | 2–4 ngày | **Vài giờ** |
| Lập 1 ma trận đề thi cân chuẩn | 3–6 giờ | **Vài phút** |
| Gom minh chứng phủ chuẩn cho 1 ngành | Hàng tuần, cuống cuồng | **Tức thời, sẵn sàng quanh năm** |
| Rà soát chất lượng học thuật | Phụ thuộc vài chuyên gia | **AI rà toàn bộ, nhất quán** |

> **Quy đổi:** chỉ cần tiết kiệm khoảng **8–10 giờ công/giảng viên/kỳ** cho một trường vài trăm giảng viên là đã **vượt xa** chi phí 300 triệu/năm — chưa kể giá trị **giảm rủi ro trượt tiêu chí kiểm định** (chi phí làm lại và uy tín là rất lớn).

---

## 7. 💰 Gói thuê trọn gói **300.000.000 đồng/năm**

Một mức giá, **toàn trường dùng**. Đã bao gồm tất cả:

### ✅ Đã bao gồm
- **Toàn bộ phân hệ** (mục 4) và **toàn bộ tính năng AI đánh giá + nâng cấp** (mục 5).
- **Không giới hạn người dùng** (giảng viên, trưởng khoa, ĐBCL, quản trị) với **phân quyền theo vai trò & phạm vi (RBAC)**.
- **Số chương trình đào tạo theo quy mô toàn trường** (thỏa thuận theo thực tế triển khai).
- **Vận hành trên hạ tầng đám mây** do nhà cung cấp quản lý: máy chủ, cơ sở dữ liệu, lưu trữ file, sao lưu định kỳ, giám sát, cập nhật phần mềm liên tục.
- **Chi phí xử lý AI** ở mức sử dụng hợp lý cho vận hành thường xuyên của một trường.
- **Triển khai & đào tạo ban đầu**: thiết lập hệ thống, cấu hình mẫu đề cương riêng của trường, import dữ liệu CTĐT mẫu, **tập huấn người dùng theo vai trò**.
- **Hỗ trợ kỹ thuật** trong giờ hành chính + **đồng hành 1 đợt cao điểm kiểm định/năm**.
- **Bản cập nhật tính năng mới** phát hành trong năm — miễn phí.

### 💡 Tùy chọn nâng cấp (báo giá riêng)
- Tích hợp **SSO/LDAP** của trường; xuất file theo **mẫu thương hiệu** riêng; quy trình duyệt tùy biến.
- **Triển khai on-premise** (cài trong hạ tầng của trường, toàn quyền kiểm soát dữ liệu) — chuyển sang mô hình **license + bảo trì**; trường dùng API key AI riêng.
- Hỗ trợ **ưu tiên 24/7** và cán bộ phụ trách riêng cho mùa kiểm định nhiều đợt.

### 🧾 Điều khoản thương mại gợi ý
- **Chu kỳ:** 12 tháng, gia hạn hằng năm. Ưu đãi khi **cam kết 2–3 năm**.
- **Thanh toán:** trọn năm hoặc theo 2 kỳ; xuất hóa đơn VAT đầy đủ.
- **Dùng thử:** **30–60 ngày thí điểm 1 khoa** trước khi ký hợp đồng năm.

---

## 8. An toàn, tin cậy & tuân thủ

- **Ngôn ngữ chính tiếng Việt**, giao diện song ngữ Việt/Anh — phù hợp hồ sơ AUN-QA.
- **Phân quyền chặt theo vai trò & phạm vi**; **audit log** toàn bộ thao tác quan trọng.
- **Soft-delete + lưu trữ (archive)** cho tài liệu đã ban hành — không xóa cứng; **versioning** đầy đủ.
- **Sao lưu định kỳ**, khôi phục dữ liệu; cập nhật bảo mật liên tục.
- **Human-in-the-loop:** AI hỗ trợ, con người quyết định — dữ liệu học thuật luôn thuộc về trường.

---

## 9. Đối tượng phù hợp

- Trường/khoa đang **chuyển đổi sang OBE** hoặc **chuẩn bị kiểm định AUN-QA / MOET**.
- Phòng **Đảm bảo chất lượng**, **Đào tạo**, và **đội ngũ giảng viên** muốn chuẩn hóa quy trình.
- Trường có **nhiều ngành, nhiều giảng viên** cần đồng bộ chất lượng và tiết kiệm thời gian.

---

## 10. Lộ trình triển khai (gợi ý)

| Giai đoạn | Thời gian | Nội dung |
|---|---|---|
| **Khởi động** | Tuần 1–2 | Cài đặt, tạo tài khoản, cấu hình mẫu của trường |
| **Nạp dữ liệu** | Tuần 2–4 | Trích xuất đề án/CTĐT mẫu bằng AI, rà soát PLO/PI/học phần |
| **Thí điểm** | Tháng 2 | 1–2 khoa soạn đề cương/ngân hàng/đề thi thực tế |
| **Nhân rộng** | Tháng 3+ | Mở rộng toàn trường, tập huấn theo đợt |
| **Đồng hành kiểm định** | Theo lịch | Báo cáo phủ chuẩn, đóng gói minh chứng |

---

## 11. Kêu gọi hành động

> **Đăng ký demo 60 phút** và **gói thí điểm 1 khoa** để trải nghiệm trực tiếp: tải một đề án mở ngành lên, để AI dựng PLO/PI/học phần, soạn một đề cương đạt chuẩn — rồi để AI **chấm điểm và tự nâng cấp** ngay trước mắt bạn.

**EduOBE — Đào tạo theo chuẩn đầu ra, kiểm định trong tầm tay.**

*Liên hệ: [tên đầu mối] · [email] · [điện thoại] · [website]*
