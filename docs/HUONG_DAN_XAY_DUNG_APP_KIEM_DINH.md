# Hướng dẫn cho Claude Code — Xây dựng Hệ thống Kiểm định AUN-QA

> Tài liệu này đúc kết kinh nghiệm thực chiến từ việc xây dựng nền tảng EduOBE/AIOBE
> (quản lý OBE/AUN-QA, multi-tenant, tích hợp AI, deploy Cloud Run + Cloud SQL).
> Mục tiêu: giúp Claude Code xây "app tiếp theo" (Hệ thống kiểm định CTĐT theo chuẩn
> AUN-QA, kiến trúc đa-tiêu-chuẩn) **nhanh, đúng, và KHÔNG lặp lại các lỗi đã từng trả giá**.
> Đặc tả chức năng đầy đủ của app mới nằm ở file `Mo_ta_chuc_nang_App.docx` — đọc nó trước,
> tài liệu này bổ sung phần "làm thế nào cho đúng".

---

## 0. Cách dùng tài liệu này

- Nạp file này vào **Project** (cùng với `Mo_ta_chuc_nang_App.docx`) làm tài liệu nền.
- Yêu cầu Claude Code: "Đọc cả hai tài liệu, rồi tạo `CLAUDE.md` cho repo mới dựa trên mục 13 ở đây trước khi viết code."
- **Làm theo từng phase nhỏ.** Bài học đắt nhất ở app trước: sinh quá nhiều code một lúc rồi
  phải vá ngược. Mỗi phase phải *chạy được + có test + có migration* rồi mới sang phase sau.
- Hai tài liệu phân vai rõ: `Mo_ta_chuc_nang_App.docx` = "xây **cái gì**"; tài liệu này = "xây **thế nào** để không vỡ".

---

## 1. Mười bài học đắt giá nhất (đọc kỹ trước khi gõ dòng code đầu tiên)

1. **Multi-tenant phải thiết kế từ ngày 0, không bao giờ bolt-on về sau.**
   Ở app trước, multi-tenant bị thêm vào muộn (cả một chiến dịch C0–C5): phải viết migration
   thêm `tenant_id` cho 28 bảng, vá rò rỉ dữ liệu giữa các trường, sửa lại toàn bộ truy vấn.
   App mới *mặc định* nhiều trường → **mọi bảng nghiệp vụ có `tenant_id` ngay từ schema đầu tiên.**

2. **Test phải chạy trên đúng loại DB của production (PostgreSQL), không chỉ SQLite.**
   Bài học cay đắng: RLS, ràng buộc `NOT NULL`, unique-theo-tenant, ON DELETE… là *no-op trên
   SQLite*. App trước "67 test xanh" trên SQLite nhưng vẫn 500 trên Postgres. Phải có CI chạy
   test trên Postgres thật trước khi tin tưởng.

3. **Connection pool + biến phiên (SET LOCAL / session GUC) là cái bẫy gây 500 chập chờn.**
   Login lúc được lúc 500 do `SET LOCAL` cho RLS để lại trạng thái bẩn trên connection được
   tái sử dụng từ pool. Quy tắc: **luôn rollback khi request lỗi** để không "đầu độc" connection;
   biến phiên phải set lại đầu mỗi request và bọc trong transaction; bật RLS sau một cờ cấu hình
   để có thể tắt nhanh khi sự cố.

4. **Bộ lọc theo tenant phải dùng biểu thức trực tiếp, KHÔNG dùng lambda bị cache.**
   Lỗi rò rỉ dữ liệu nguy hiểm nhất app trước: bộ lọc tenant viết bằng lambda bị ORM cache lại
   giá trị tenant đầu tiên → trường B nhìn thấy dữ liệu trường A. Với Prisma: dùng middleware/
   extension chèn `where: { tenantId }` từ context theo *từng request*, đừng đóng băng giá trị.

5. **AI là một "lớp dịch vụ" có kiểm soát, không phải lời gọi API rải rác.**
   Tách hẳn một lớp LLM: abstraction nhiều nhà cung cấp, key mã hóa theo tenant, validate output
   bằng schema, retry/backoff, giới hạn concurrency, đo token & chi phí, hạn mức theo ngày.
   App trước phải gom các lời gọi rải rác lại thành một lớp duy nhất về sau — tốn công.

6. **AI luôn human-in-the-loop; output AI luôn là "bản nháp" cho tới khi người duyệt.**
   Không để AI tự ghi vào bản chính thức. Mọi nội dung AI sinh phải được đánh dấu nguồn = AI,
   lưu lịch sử, và chỉ vào SAR chính thức sau khi người phụ trách duyệt. (Đặc tả app mới yêu cầu
   đúng điều này — hãy enforce bằng kiến trúc, không chỉ bằng UI.)

7. **Lưu file phải qua một lớp trừu tượng (local ở dev, object storage ở prod) ngay từ đầu.**
   Cloud Run/môi trường container là *ephemeral* — file ghi xuống đĩa sẽ mất. App trước phải
   refactor để đưa file lên GCS. App mới: interface `Storage` với 2 driver (local + S3/GCS) từ ngày 0.

8. **Chịu tải phải thiết kế sẵn, không vá sau.** Index cho cột lọc/khóa ngoại, phân trang bắt buộc
   ở mọi list endpoint, connection pool có cấu hình, tác vụ nặng (sinh báo cáo, gọi AI hàng loạt,
   xuất file) đẩy sang background job. App trước gom thành "Nhóm A/B" để vá hiệu năng về sau.

9. **Phản hồi rỗng (204/empty body) phải xử lý ở client.** Một lỗi nhỏ nhưng gây "Unexpected end
   of JSON input" khắp nơi khi DELETE trả 204 mà client cứ `res.json()`. API client phải trả
   `null` cho body rỗng, và bọc lỗi mạng kèm URL để debug.

10. **Kỷ luật migration + đóng gói + đổi log.** Mỗi thay đổi schema kèm đúng một migration; mọi
    thao tác quan trọng vào audit log; tài liệu đã ban hành → soft-delete/archive, **không xóa cứng**;
    đóng gói bằng archive sạch (loại `node_modules`, build cache, file DB, …) theo tag phiên bản.

---

## 2. Nguyên tắc kiến trúc bắt buộc (thiết kế từ ngày 0)

Những thứ sau **không được để "làm sau"** — chi phí thêm vào muộn lớn gấp nhiều lần:

| Hạng mục | Vì sao bắt buộc từ đầu | Hệ quả nếu bỏ qua (đã gặp ở app trước) |
|---|---|---|
| `tenant_id` trên mọi bảng nghiệp vụ | Cách ly dữ liệu nhiều trường | Phải migrate 28 bảng + sửa toàn bộ query |
| Lớp Storage trừu tượng | Container ephemeral | Mất file, phải refactor lên GCS |
| Lớp LLM thống nhất | Kiểm soát chi phí/khóa/chất lượng | Lời gọi rải rác, khó đo, khó đổi nhà cung cấp |
| Audit log | Yêu cầu kiểm định + truy vết | Không truy được "ai sửa gì khi nào" |
| Soft-delete + versioning | Tài liệu ban hành không được mất | Xóa nhầm không khôi phục được |
| Phân trang + index | Dữ liệu trường lớn | Trang treo, query chậm khi nhiều CTĐT |
| i18n VI/EN | UI song ngữ | Hard-code chuỗi, sửa lại toàn bộ |
| Cờ cấu hình (RLS, AI on/off, job mode) | Bật/tắt khi sự cố | Không thể tắt RLS khi prod 500 |

---

## 3. Multi-tenant đúng cách (phần đau nhất ở app trước — đọc kỹ)

App mới mặc định nhiều trường đại học. Thiết kế:

- **Mô hình:** shared-schema + cột `tenant_id` trên mọi bảng nghiệp vụ. (Đơn giản, rẻ, đủ cách ly
  nếu enforce đúng.) Có thể nâng lên schema-per-tenant sau nếu cần, nhưng đừng bắt đầu phức tạp.
- **Phân giải tenant theo request:** từ subdomain (`<truong>.tenmien.vn`) hoặc header `X-Tenant`,
  lưu vào một context theo request (AsyncLocalStorage ở Node/Next.js). **Không** dùng biến toàn cục.
- **Chèn bộ lọc tự động:** dùng Prisma Client Extension (`$extends` / middleware) để chèn
  `where: { tenantId }` cho mọi `findMany/findFirst/update/delete` và gán `tenantId` khi `create`.
  Lấy `tenantId` từ context *tại thời điểm gọi*, **không** đóng băng trong closure (xem bài học #4).
- **Phòng thủ chiều sâu:** nếu dùng Postgres RLS, bật sau cờ `RLS_ENABLED`; set GUC
  (`SET app.tenant_id`) đầu mỗi transaction và **rollback khi lỗi** (bài học #3). RLS là *lớp lưới
  an toàn thứ hai*, không thay cho lọc ở tầng ứng dụng.
- **Super-admin xuyên tenant** cần đường đi riêng (bỏ qua bộ lọc) và **chỉ** super-admin mới vào
  được endpoint quản trị nền tảng. App trước từng để admin-của-trường lọt vào API super-admin →
  phải vá logic phân quyền. Quyết định ranh giới quyền *trước*, không sửa sau.
- **Kiểm thử cách ly là bắt buộc:** viết test "trường A không bao giờ thấy dữ liệu trường B" và
  chạy **trên Postgres**. Có script pen-test RLS riêng chạy ở staging trước khi bật RLS ở prod.
- **Billing theo thời gian:** mỗi tenant có `valid_until`; super-admin gia hạn/khóa. Middleware
  chặn tenant hết hạn (trả 403 rõ ràng, không 500).

---

## 4. Lớp AI/LLM đúng cách

Đặc tả app mới có rất nhiều AI (phân tích tiêu chí, gợi ý minh chứng, viết nháp SAR, chatbot RAG,
mock interview). Gói tất cả sau **một lớp service duy nhất**:

- **Abstraction đa nhà cung cấp:** một interface, đổi được OpenAI/Azure/Gemini/Claude/local LLM
  bằng cấu hình. Đặc tả app mới chốt "OpenAI-compatible abstraction" — tôn trọng điều đó.
- **Khóa API theo tenant, mã hóa khi lưu** (ví dụ Fernet/KMS), có prefix phiên bản để xoay khóa;
  tương thích ngược với khóa cũ.
- **Validate output bằng schema (Zod/Pydantic) trước khi dùng.** Ép model trả JSON thuần; nếu sai
  schema → retry rồi báo lỗi, **không** ghi dữ liệu rác vào DB.
- **Độ bền:** retry + backoff; giới hạn concurrency toàn cục và **semaphore công bằng theo tenant**
  để một trường không "ăn" hết quota; timeout rõ ràng.
- **Kiểm soát chi phí:** ghi token in/out + chi phí mỗi lời gọi, gắn tenant; hạn mức token/ngày
  theo tenant; có trang xem chi phí cho admin.
- **RAG có phân quyền:** chatbot chỉ truy xuất dữ liệu user được phép xem (lọc theo tenant + quyền
  *trước* khi đưa vào ngữ cảnh). pgvector là đủ cho MVP — đừng vội thêm vector DB riêng.
- **Quản trị AI (đặc tả mục 6):** bật/tắt AI theo module; đánh dấu nội dung do AI sinh; lưu lịch sử
  prompt/response; audit log thao tác AI quan trọng; không gửi dữ liệu nhạy cảm ra ngoài nếu chưa
  cấu hình cho phép. Enforce bằng kiến trúc.

---

## 5. Chịu tải & hiệu năng (thiết kế sẵn)

- **Index** cho mọi cột dùng để lọc/sắp xếp/khóa ngoại — đặc biệt `tenant_id` đi kèm các cột lọc
  (index tổ hợp `(tenant_id, …)`).
- **Phân trang bắt buộc** ở mọi list (cursor hoặc offset + tổng số); không có endpoint "trả tất cả".
- **Connection pool** cấu hình tường minh (size, timeout, recycle); ở serverless dùng pooler
  (PgBouncer/Prisma Accelerate/Data Proxy) để tránh cạn connection.
- **Background jobs** (BullMQ hoặc tương đương) cho: sinh SAR/báo cáo, xuất Word/PDF/Excel, gọi AI
  hàng loạt, đóng gói minh chứng. Có polling tiến độ. Hỗ trợ chế độ chạy inline ở dev cho dễ test.
- **Upload nhiều file** (kho minh chứng) phải stream, giới hạn kích thước, quét trùng (hash).

---

## 6. Dữ liệu, migration & toàn vẹn

- **Mỗi thay đổi schema = đúng một migration** (Prisma Migrate). Không sửa DB tay.
- **Trường chuẩn cho mọi bảng chính** (đặc tả mục 8): `id, tenant_id, created_at, updated_at,
  created_by, updated_by, status, deleted_at`. Tạo sẵn một base/mixin để khỏi lặp.
- **Soft-delete + archive** cho tài liệu đã ban hành (SAR chính thức, minh chứng). Không xóa cứng.
- **Versioning + vòng đời trạng thái** cho CTĐT, đề cương, SAR, minh chứng (đặc tả mục 4.13 có sẵn
  danh sách trạng thái — model hóa thành state machine, chặn chuyển trạng thái không hợp lệ).
- **Audit log** cho mọi thao tác quan trọng (tạo/sửa/xóa/duyệt/chấm điểm/thao tác AI).
- **Cấu hình bộ tiêu chuẩn bằng dữ liệu, không hard-code** (đặc tả mục 2 & 4.3): bảng
  `accreditation_standards / standard_versions / criteria / requirements / indicators /
  rating_scales / suggested_evidences`. Như vậy thêm bộ tiêu chuẩn Bộ GD&ĐT sau này = nạp dữ liệu,
  không sửa code lõi. **Đây là quyết định kiến trúc quan trọng nhất của app mới — làm đúng từ đầu.**
- **Seed idempotent:** seed vai trò, quyền, bộ tiêu chuẩn AUN-QA v4.0 + 8 tiêu chí, và bootstrap
  tài khoản super-admin — chạy lại nhiều lần không nhân bản, và *vẫn* tạo super-admin trên DB đã có
  dữ liệu (app trước thiếu điều này → prod không có super-admin).

---

## 7. Frontend

- **API client chắc chắn:** trả `null` cho 204/empty body (tránh lỗi parse JSON); bọc lỗi mạng kèm
  URL; tự gắn `Authorization` + `X-Tenant`; đọc tenant từ subdomain hoặc `?tenant=` (cơ chế test
  trường con rất hữu ích khi chưa có nhiều subdomain).
- **i18n VI/EN** từ đầu; tiếng Việt là ngôn ngữ chính. Không hard-code chuỗi.
- **Hệ thống component nhất quán:** định nghĩa sớm `card / btn / badge / input` (Tailwind layer) để
  UI đồng nhất; sidebar menu theo đặc tả mục 7; bảng dữ liệu có tìm kiếm/lọc/sắp xếp/phân trang dùng
  chung một component.
- **AI assistant đặt cạnh nội dung đang soạn** (panel bên), không phải trang riêng tách rời — đúng
  trải nghiệm "viết SAR có AI hỗ trợ".
- **Responsive** desktop/tablet/mobile.

---

## 8. Bảo mật

- JWT mang `tenant_id` + vai trò; mật khẩu hash bcrypt/argon2.
- **RBAC khai báo bằng dữ liệu** (roles/permissions/user_roles theo đặc tả) — kiểm tra quyền ở
  server cho mọi endpoint, không tin client.
- CORS: cấu hình bằng regex cho subdomain động; xử lý đúng `allow_credentials` (không dùng `*` khi
  gửi cookie/credential). App trước "Failed to fetch" vì preflight bị chặn — cấu hình CORS sớm.
- Phân quyền dữ liệu AI/RAG (mục 4). Không log khóa/bí mật ra console.
- Exception handler toàn cục **ghi traceback** (app trước mù thông tin khi prod 500 vì không log).

---

## 9. Quy trình build theo phase (đề xuất, đã trộn bài học)

Tuân thủ nguyên tắc "MVP chạy được trước, AI/RAG cuối cùng" (đặc tả mục 12 & 13). Mỗi phase phải
đạt "Definition of Done" ở mục 10 trước khi sang phase sau.

- **P0 — Nền móng:** repo + `CLAUDE.md` + Docker compose (Postgres) + cấu trúc thư mục + cấu hình
  cờ (RLS/AI/job mode). Lớp **multi-tenant context + Prisma extension lọc tenant** (làm ngay đây,
  không để sau). Lớp **Storage** (local+S3). Health check.
- **P1 — Auth + RBAC + tenant + seed:** đăng nhập, JWT, RBAC khai báo, quản lý user/khoa/bộ môn,
  bootstrap super-admin, billing `valid_until`. Test cách ly tenant **trên Postgres**.
- **P2 — Cấu hình bộ tiêu chuẩn (data-driven):** schema standards/criteria/requirements + seed
  AUN-QA v4.0 + 8 tiêu chí + thang 7 mức. Đây là xương sống đa-tiêu-chuẩn.
- **P3 — Chương trình đào tạo + OBE:** CTĐT (đa phiên bản), PEO/PLO/CLO, học phần, đề cương, các
  ma trận (PLO-CLO, PLO-học phần, phương pháp dạy/đánh giá), cảnh báo độ phủ.
- **P4 — Đợt tự đánh giá + SAR:** assessment cycle, SAR theo 8 tiêu chí, nhập liệu từng tiêu chí,
  vòng đời trạng thái, đánh giá nội bộ + chấm điểm.
- **P5 — Minh chứng:** kho minh chứng tập trung, upload nhiều file, tự đánh mã, liên kết một minh
  chứng với nhiều tiêu chí, tìm/lọc, trạng thái xác minh, chống trùng.
- **P6 — Dashboard + Nhiệm vụ + Kế hoạch cải tiến (PDCA):** dashboard 3 cấp, Kanban/calendar nhiệm
  vụ, kế hoạch cải tiến + KPI.
- **P7 — Xuất báo cáo:** SAR ra Word/PDF, danh mục minh chứng ra Excel, gói minh chứng (zip theo
  tiêu chí) — chạy bằng background job.
- **P8 — Lớp AI (cuối cùng):** lớp LLM thống nhất, tóm tắt/gợi ý minh chứng, viết nháp SAR (đánh dấu
  nháp + human-in-the-loop), kiểm tra khoảng trống, rồi mới tới chatbot RAG + mock interview.
- **P9 — Nâng cao:** import đề cương Word/Excel, khảo sát bên liên quan, tích hợp LMS/SIS/HRM, bổ
  sung bộ tiêu chuẩn Bộ GD&ĐT (chỉ nạp dữ liệu nhờ thiết kế P2).

> Quan trọng: **đừng yêu cầu Claude Code làm nhiều phase một lượt.** Mỗi lần một phase, review, rồi
> tiếp. Đây là cách tránh đúng cái bẫy "sinh quá nhiều code khó kiểm soát" của app trước.

---

## 10. Definition of Done cho mỗi phase

Một phase chỉ "xong" khi tất cả các mục sau đạt:

- [ ] Chạy được local (migrate + seed + khởi động không lỗi).
- [ ] Có migration cho mọi thay đổi schema (không sửa DB tay).
- [ ] Có test logic nghiệp vụ + **test cách ly tenant**, chạy **trên Postgres** (không chỉ SQLite).
- [ ] List endpoint có phân trang; cột lọc/khóa ngoại có index.
- [ ] Thao tác quan trọng ghi audit log.
- [ ] Không xóa cứng tài liệu ban hành (soft-delete).
- [ ] Lỗi server có log traceback; request lỗi có rollback (không đầu độc pool).
- [ ] Chuỗi UI qua i18n; phản hồi rỗng xử lý đúng ở client.
- [ ] Cập nhật `CHANGELOG.md` + tài liệu.

---

## 11. Đóng gói & Deploy

- **Cloud Run + Cloud SQL (Postgres):** container ephemeral → file lên object storage; chạy
  `migrate deploy` + seed lúc khởi động; biến môi trường cho secret (không commit secret).
- **Cấu hình bằng env + cờ:** `RLS_ENABLED`, `AI_ENABLED`, `JOB_MODE`, pool size, base domain,
  CORS regex, khóa mã hóa… để bật/tắt nhanh khi sự cố.
- **Đóng gói sạch theo tag phiên bản:** archive loại bỏ `node_modules`, `.next`, file DB,
  cache, `.git`, thư mục storage. Có `CHANGELOG.md` cho mỗi phiên bản.
- **Bài học vận hành:** trước khi bật RLS ở prod, chạy script pen-test RLS trên **staging Postgres**.
  Sau khi sửa lỗi, **phải deploy lại nhánh mới nhất** — đừng để prod chạy code cũ (app trước từng
  vá xong nhưng prod vẫn chạy bản cũ còn bug đăng nhập).

---

## 12. Checklist chống lỗi (in ra dán lên tường)

Tất cả mục dưới là lỗi **đã thực sự xảy ra** ở app trước — đừng lặp lại:

- [ ] `tenant_id` có mặt trên **mọi** bảng nghiệp vụ ngay từ migration đầu.
- [ ] Bộ lọc tenant dùng giá trị từ context theo request, **không** lambda/closure bị cache.
- [ ] Có rollback khi request lỗi (không để connection pool bị "đầu độc").
- [ ] Biến phiên/RLS set lại đầu mỗi transaction; RLS bật sau cờ; tắt được nhanh.
- [ ] Test chạy trên **Postgres**, không chỉ SQLite (RLS/NOT NULL/unique là no-op trên SQLite).
- [ ] API client trả `null` cho 204/empty; bọc lỗi mạng kèm URL.
- [ ] File lưu qua lớp Storage (không ghi thẳng đĩa container).
- [ ] Output LLM validate schema trước khi dùng; nội dung AI = nháp tới khi người duyệt.
- [ ] Khóa AI mã hóa khi lưu; có hạn mức token/chi phí theo tenant.
- [ ] List có phân trang; cột lọc có index.
- [ ] Chỉ super-admin vào endpoint quản trị nền tảng; ranh giới quyền chốt trước.
- [ ] Seed super-admin idempotent, chạy được cả trên DB đã có dữ liệu.
- [ ] CORS regex + `allow_credentials` đúng; exception handler log traceback.
- [ ] Bộ tiêu chuẩn là **dữ liệu cấu hình**, không hard-code AUN-QA.
- [ ] Soft-delete + versioning + audit log cho tài liệu ban hành.

---

## 13. Mẫu `CLAUDE.md` cho repo mới (dán và chỉnh)

```markdown
# CLAUDE.md — Hệ thống Kiểm định CTĐT (AUN-QA, đa tiêu chuẩn)

## Bối cảnh
Nền tảng kiểm định CTĐT đại học, ưu tiên AUN-QA Programme v4.0, kiến trúc đa-tiêu-chuẩn
(thêm chuẩn Bộ GD&ĐT sau bằng cấu hình dữ liệu). Đặc tả: `Mo_ta_chuc_nang_App.docx`.
Hướng dẫn thực chiến (bài học từ app trước): `HUONG_DAN_XAY_DUNG_APP_KIEM_DINH.md`.
ĐỌC CẢ HAI trước khi thay đổi nghiệp vụ.

## Nguyên tắc bắt buộc
- Multi-tenant từ ngày 0: `tenant_id` trên mọi bảng; lọc tenant theo context-per-request
  (KHÔNG lambda cache); RLS sau cờ; rollback khi lỗi.
- Test trên Postgres (không chỉ SQLite). Có test cách ly tenant.
- Bộ tiêu chuẩn = dữ liệu cấu hình, không hard-code.
- AI là lớp service: validate output, key mã hóa theo tenant, retry/concurrency/quota,
  human-in-the-loop, nội dung AI = nháp tới khi duyệt.
- Storage qua abstraction (local/S3). Soft-delete + versioning + audit log.
- List phân trang + index. i18n VI/EN. Client xử lý 204/empty.

## Kiến trúc
- Frontend/Backend: Next.js + TypeScript + Tailwind (API routes hoặc NestJS).
- DB: PostgreSQL + Prisma. Auth: Auth.js + RBAC khai báo. RAG: pgvector.
- Jobs: BullMQ. Xuất: docx/ExcelJS/PDF. Storage: local→S3.

## Quy ước code
- Trường chuẩn mọi bảng: id, tenant_id, created_at, updated_at, created_by, updated_by,
  status, deleted_at.
- Mỗi thay đổi schema kèm 1 migration. Logic nghiệp vụ có unit test.
- Output LLM validate bằng Zod trước khi dùng; ép JSON thuần.

## Quy trình
- Làm theo từng phase nhỏ (xem mục 9 tài liệu hướng dẫn). MVP chạy được trước, AI/RAG cuối.
- Mỗi phase đạt "Definition of Done" (mục 10) rồi mới sang phase sau.
```

---

*Tài liệu kết thúc. Đưa file này cùng `Mo_ta_chuc_nang_App.docx` vào Project, yêu cầu Claude Code
sinh `CLAUDE.md` theo mục 13, rồi build theo phase ở mục 9.*
