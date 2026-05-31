# EduOBE — Nền tảng Quản lý Đào tạo theo Chuẩn đầu ra (OBE) & Kiểm định AUN-QA

> **Số hóa toàn bộ chuỗi học thuật — từ Đề án mở ngành đến từng Đề thi — trên một nền tảng duy nhất, có Trí tuệ Nhân tạo đồng hành và truy vết chuẩn đầu ra xuyên suốt.**

---

## 1. Vì sao các trường cần EduOBE?

Chuyển đổi sang đào tạo theo chuẩn đầu ra (Outcome-Based Education) và chuẩn bị kiểm định **AUN-QA / MOET** đang là áp lực lớn với mọi cơ sở giáo dục đại học. Nhưng thực tế tại hầu hết các trường:

### 😣 Những nỗi đau quen thuộc

| Nỗi đau | Hậu quả |
|---|---|
| **Đề cương, ma trận, đề thi nằm rải rác** trong hàng nghìn file Word/Excel của từng giảng viên | Không kiểm soát được phiên bản, thất lạc minh chứng, mỗi người một mẫu |
| **Mất "tính nhất quán dọc" (constructive alignment)** — CLO không gắn PLO, đánh giá không phủ hết CLO | Bị đoàn kiểm định "bắt lỗi", phải làm lại từ đầu |
| **Soạn ma trận đề thi, đề cương, ngân hàng câu hỏi thủ công** | Tốn hàng trăm giờ công của giảng viên mỗi kỳ |
| **Trích xuất PLO/PI/học phần từ đề án mở ngành dày hàng trăm trang bằng tay** | Sai sót, mất thời gian, khó đối chiếu |
| **Đến kỳ kiểm định mới cuống cuồng gom minh chứng** | Áp lực dồn cục, báo cáo phủ chuẩn không kịp, thiếu dữ liệu |
| **Không trả lời được câu hỏi: "PLO này được đánh giá ở đâu? Câu hỏi nào đo CLO kia?"** | Mất điểm ở tiêu chí cốt lõi của AUN-QA |

### 💡 EduOBE giải quyết tận gốc

EduOBE là **hệ thống quản trị học thuật chuyên biệt cho OBE/AUN-QA**, đưa toàn bộ quy trình lên một nền tảng web duy nhất, **đảm bảo truy vết hai chiều xuyên suốt** và **dùng AI để tự động hóa các công việc nặng nhọc nhất** — đồng thời luôn giữ con người là người quyết định cuối cùng.

---

## 2. Chuỗi giá trị xuyên suốt — "một mạch" từ trên xuống dưới

```
   Đề án mở ngành (PDF/DOCX)
        │  ✨ AI trích xuất tự động
        ▼
   Chương trình đào tạo → PLO → PI → Danh mục học phần
        │  ✨ AI soạn đề cương theo chuẩn AUN-QA
        ▼
   Đề cương học phần → CLO → Ma trận CLO×PLO → Đánh giá (kèm Rubric) → Kế hoạch dạy
        │  ✨ AI biên soạn giáo trình
        ▼
   Giáo trình theo chương (gắn CLO)
        │  ✨ AI sinh ngân hàng câu hỏi
        ▼
   Ngân hàng câu hỏi (CLO + Bloom + độ khó) → Ma trận đề thi
        │  Tự động bốc đề, nhiều mã đề
        ▼
   Đề thi + Đáp án + Bảng đặc tả
        │
        ▼
   Kho minh chứng & Báo cáo phủ chuẩn AUN-QA
```

**Điểm khác biệt cốt lõi:** mọi mắt xích đều được **ràng buộc dữ liệu với nhau**. Khi bạn hỏi *"PLO2 được đo bằng câu hỏi nào, ở học phần nào?"* — hệ thống trả lời trong vài giây, không cần lục file.

---

## 3. Các phân hệ chính

### 🤖 3.1. Trích xuất Đề án mở ngành bằng AI
- Tải lên đề án/CTĐT (**PDF, DOCX**, kể cả **file scan** nhờ OCR tiếng Việt).
- AI tự động trích xuất có cấu trúc: **thông tin ngành, danh sách PLO, PI, danh mục học phần, ma trận học phần–PLO** — kể cả dữ liệu nằm trong **bảng biểu**.
- **Con người rà soát & xác nhận** (human-in-the-loop): kết quả hiển thị cạnh văn bản gốc để sửa trước khi ghi vào hệ thống — **không bao giờ tự ý ghi đè**.
- *Giá trị: rút ngắn việc nhập liệu từ vài ngày xuống vài phút.*

### 🎯 3.2. Quản lý CTĐT & Chuẩn đầu ra
- CRUD chương trình đào tạo, PLO, PI, học phần.
- **Ma trận Học phần × PLO** tương tác (mức I/R/M – Introduce/Reinforce/Master).
- **Cảnh báo độ phủ tự động**: PLO nào chưa có học phần "Master", PLO nào bị bỏ sót.

### 📋 3.3. Đề cương học phần — có AI & kiểm tra Alignment
- Soạn đề cương đầy đủ: CLO, ma trận CLO×PLO, phương pháp dạy-học, **đánh giá kèm Rubric chi tiết**, kế hoạch giảng dạy theo tuần.
- **✨ AI soạn đề cương** căn cứ CTĐT, PLO, PI, **mẫu đề cương của trường** và **tài liệu chuẩn AUN-QA** (tải lên tùy chọn). Tùy chỉnh số CLO, số tuần, cơ cấu đánh giá, **CLO song ngữ Việt–Anh**.
- **Kiểm tra alignment tự động:** mỗi CLO phải gắn ≥1 PLO; mỗi CLO phải được đánh giá; tổng trọng số = 100%; cảnh báo CLO không được giảng dạy. **Bắt buộc đạt trước khi phê duyệt.**
- **Vòng đời & phiên bản:** Draft → Submitted → Approved → Published → Archived, có **so sánh phiên bản (diff)** và nhật ký duyệt.
- **Xuất DOCX** theo mẫu của trường.

### 📚 3.4. Giáo trình / Tài liệu học phần — biên soạn bằng AI
- Soạn giáo trình theo chương, mỗi chương gắn CLO.
- **✨ AI tạo cả giáo trình** (dàn ý chương + nội dung chi tiết) hoặc **viết nội dung từng chương** dựa trên CLO.
- Quản lý phiên bản; **xuất DOCX và PDF** (hỗ trợ đầy đủ tiếng Việt).

### 🏦 3.5. Ngân hàng câu hỏi & Ma trận đề thi — sinh câu hỏi bằng AI
- CRUD câu hỏi (trắc nghiệm, điền khuyết, tự luận, bài tập…), mỗi câu gắn **CLO + mức Bloom + độ khó**.
- **✨ AI sinh câu hỏi** bám sát CLO của đề cương, phân bổ theo Bloom & độ khó.
- **Import/Export CSV & Excel**.
- **Thống kê phát hiện "lỗ hổng"**: thiếu câu mức Vận dụng cho CLO nào, mất cân đối ở đâu.
- **Ma trận đề thi** phân bố theo (CLO × Bloom × độ khó).

### 📝 3.6. Tạo đề thi tự động
- Sinh đề từ ma trận: hệ thống **tự bốc câu hỏi** đúng số lượng mỗi ô, **tránh trùng**, sinh **nhiều mã đề**.
- Chỉnh tay: **thay câu, khóa câu** sau khi sinh.
- Tự sinh **đáp án/barem** và **bảng đặc tả đề thi (test blueprint)** làm minh chứng.
- **Xuất đề thi + đáp án ra DOCX**. Vòng đời: Draft → Reviewed → Approved → Published.

### 🗄️ 3.7. Kho minh chứng & Kiểm định AUN-QA
- Lưu mọi phiên bản đề cương, giáo trình, ngân hàng, đề thi, đề án gốc.
- **Báo cáo phủ chuẩn (coverage report):** ma trận tổng hợp PLO → PI → CLO → đánh giá, **chỉ rõ điểm thiếu** cần bổ sung.
- **Xuất gói minh chứng (ZIP)** phục vụ đoàn kiểm định.
- **Nhật ký kiểm toán (audit log) đầy đủ**: ai – làm gì – khi nào – phiên bản nào.

---

## 4. Lợi ích định lượng

| Trước EduOBE | Với EduOBE |
|---|---|
| Soạn 1 đề cương đạt chuẩn: **1–2 ngày** | **15–30 phút** (AI soạn + giảng viên rà soát) |
| Nhập PLO/PI/học phần từ đề án 100+ trang: **2–3 ngày** | **vài phút** + rà soát |
| Gom minh chứng kiểm định: **hàng tuần cao điểm** | **Xuất gói minh chứng tức thì** |
| Soạn 100 câu hỏi ngân hàng: **nhiều ngày** | **AI sinh hàng loạt** theo CLO/Bloom |
| Trả lời "PLO này đo ở đâu?": **mò file thủ công** | **Báo cáo phủ chuẩn tự động** |
| Kiểm tra alignment: **rà bằng mắt, dễ sót** | **Cảnh báo tự động, chặn duyệt nếu chưa đạt** |

---

## 5. Phân quyền theo vai trò (RBAC)

| Vai trò | Quyền chính |
|---|---|
| **Admin hệ thống** | Quản trị người dùng, danh mục, cấu hình |
| **Quản lý CTĐT** (Trưởng khoa/Bộ môn) | Tạo/duyệt CTĐT, PLO, PI; phân công phụ trách; duyệt đề cương, đề thi |
| **Giảng viên** | Soạn đề cương, giáo trình, câu hỏi, đề thi cho học phần được phân công |
| **Cán bộ ĐBCL/Kiểm định** | Xem toàn bộ minh chứng, xuất báo cáo phủ chuẩn, theo dõi phiên bản |
| **Khách (read-only)** | Xem tài liệu đã ban hành |

Phân quyền theo **cả vai trò lẫn phạm vi** (chỉ thao tác trên CTĐT/học phần được gán).

---

## 6. Vì sao chọn EduOBE thay vì tự làm bằng Word/Excel?

- ✅ **Chuyên biệt cho OBE/AUN-QA** — không phải công cụ văn phòng đa dụng được "uốn" cho vừa.
- ✅ **Truy vết hai chiều là bản chất của hệ thống**, không phải tính năng cộng thêm.
- ✅ **AI đồng hành ở mọi khâu nặng nhọc**, nhưng **con người luôn quyết định cuối** — an toàn cho kiểm định.
- ✅ **Sẵn sàng minh chứng mọi lúc** — không còn "mùa kiểm định" căng thẳng.
- ✅ **Chuẩn hóa toàn trường** — mọi khoa, mọi giảng viên dùng chung một quy trình, một định dạng.
- ✅ **Tiếng Việt là ngôn ngữ chính**, giao diện song ngữ Việt/Anh.

---

## 7. Công nghệ & Triển khai

- **Kiến trúc hiện đại:** Web app (Next.js) + API (FastAPI) + PostgreSQL, đóng gói Docker.
- **AI:** tích hợp Anthropic Claude — kết quả luôn được kiểm chứng cấu trúc trước khi dùng.
- **Bảo mật:** xác thực JWT, phân quyền RBAC, mã hóa khi truyền, nhật ký truy cập đầy đủ.
- **Toàn vẹn dữ liệu:** không xóa cứng tài liệu đã ban hành (soft-delete + archive), versioning & diff.
- **Linh hoạt triển khai:**
  - **Cloud (SaaS):** dùng ngay, không cần hạ tầng — chúng tôi vận hành (đã chạy trên Google Cloud Run + Cloud SQL).
  - **On-premise:** cài đặt trong hạ tầng của trường để toàn quyền kiểm soát dữ liệu.

---

## 8. Lộ trình hợp tác đề xuất

1. **Khảo sát & demo** trên dữ liệu thật của trường (1 CTĐT mẫu).
2. **Triển khai thí điểm** 1 khoa: import đề án, dựng CTĐT/PLO, soạn vài đề cương bằng AI.
3. **Đào tạo người dùng** theo từng vai trò.
4. **Nhân rộng toàn trường** + đồng hành mùa kiểm định.
5. **Hỗ trợ & cập nhật** theo thay đổi tiêu chí AUN-QA/MOET.

---

## 9. Liên hệ

> **EduOBE — Để kiểm định không còn là nỗi lo, để giảng viên tập trung vào chất lượng đào tạo.**

*Đăng ký demo miễn phí trên chính chương trình đào tạo của Quý trường.*

— *Liên hệ: [điền thông tin đội ngũ kinh doanh]*

---

<sub>Tài liệu giới thiệu sản phẩm. Các tính năng mô tả phản ánh năng lực thực tế của hệ thống tại thời điểm phát hành.</sub>
