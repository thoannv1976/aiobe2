# KẾ HOẠCH KỸ THUẬT — NHÓM C: LỚP ĐA NGƯỜI THUÊ (MULTI-TENANT)

> Mục tiêu: chuyển EduOBE/AIOBE từ **"1 trường = 1 triển khai"** sang **"1 codebase phục vụ nhiều trường đại học"** trên cùng một hạ tầng — an toàn cách ly dữ liệu, vận hành & tính phí theo từng trường.
>
> Phạm vi tài liệu: **chỉ lập kế hoạch** (chưa viết code). Bao gồm: chọn mô hình tenancy, thay đổi mô hình dữ liệu, định tuyến/định danh tenant, cách ly & bảo mật, xác thực, cấu hình theo tenant, lưu trữ, job nền, chi phí/hạn mức LLM, cấp phát vòng đời tenant, lộ trình migration, kiểm thử, quan trắc, DevOps, rủi ro, ước lượng công sức và các quyết định cần chốt.

---

## 0. Hiện trạng (điểm xuất phát)

- Backend: FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL (Cloud SQL). 28 bảng. Session DB tạo theo request qua `get_db()`.
- Auth: JWT (HS256), RBAC theo vai trò + phạm vi (bảng `assignments`).
- Hạ tầng đã có (Nhóm A/B): index, phân trang, pool DB; **lưu file qua lớp trừu tượng** (`app/services/storage.py`, GCS/cục bộ); **job nền** (`app/services/jobs.py`, bảng `jobs`); **LLM có ghi nhận usage/chi phí** (`app/services/llm.py`, bảng `llm_usage`, `app/core/llm_context.py`).
- Frontend: Next.js, gọi API qua `NEXT_PUBLIC_API_BASE`.
- **Giả định ngầm hiện tại:** toàn bộ dữ liệu thuộc về DUY NHẤT một trường. Không có khái niệm "tenant".

**Hệ quả cần xử lý:** mọi truy vấn, file, job, usage, người dùng, API key… đều phải gắn và được lọc theo **tenant_id**.

---

## 1. Chọn mô hình tenancy

| Mô hình | Mô tả | Ưu | Nhược | Phù hợp |
|---|---|---|---|---|
| **A. Shared DB – Shared schema (tenant_id)** | 1 DB, 1 schema, mỗi bảng có cột `tenant_id` | Vận hành/đơn giản nhất; chi phí thấp; migrate 1 lần cho tất cả; dễ báo cáo toàn nền tảng | Rủi ro rò rỉ chéo nếu quên filter → cần kỷ luật + RLS | **Khuyến nghị** cho quy mô ~50–200 trường |
| B. Shared DB – Schema per tenant | 1 DB, mỗi tenant 1 schema | Cách ly khá tốt; migrate theo schema | Migrate N schema phức tạp; pool/қết nối phức tạp | Trung bình |
| C. DB per tenant | Mỗi tenant 1 database/instance | Cách ly mạnh nhất; dễ tách/khôi phục theo trường | Tốn kém, vận hành nặng, khó báo cáo xuyên trường | Khi có yêu cầu pháp lý cách ly tuyệt đối |

### ➜ Quyết định khuyến nghị: **Mô hình A (shared schema + `tenant_id`)** + **Postgres Row-Level Security (RLS)** làm lớp chặn cuối (defense-in-depth).

Lý do: số lượng trường vừa phải, cần báo cáo toàn nền tảng (chi phí, sức khỏe), tối ưu chi phí hạ tầng; rủi ro rò rỉ được khắc phục bằng **2 lớp** (lọc ở tầng ứng dụng + RLS ở tầng DB). Có thể nâng cấp riêng tenant lớn lên DB-per-tenant sau (mô hình lai) mà không đổi code nghiệp vụ.

---

## 2. Thay đổi mô hình dữ liệu

### 2.1. Bảng mới `tenants`
```
tenants(
  id PK,
  code            varchar unique,        -- vd "neu", "ftu" (dùng cho subdomain)
  name            varchar,
  status          varchar,               -- active | suspended | trial | offboarding
  plan            varchar,               -- trial | standard | enterprise
  primary_domain  varchar null,          -- tên miền riêng (tùy chọn)
  settings_json   json,                  -- branding, locale, feature flags, scheme mặc định
  llm_provider    varchar null,          -- key AI riêng của trường (tùy chọn)
  contact_email   varchar,
  created_at, updated_at,
  -- giới hạn/định mức
  max_programs int null, max_users int null,
  llm_daily_token_quota int null
)
```

### 2.2. Gắn `tenant_id` cho TẤT CẢ bảng nghiệp vụ (denormalize)
Thêm `tenant_id INT NOT NULL REFERENCES tenants(id)` vào **toàn bộ** bảng dữ liệu để: (a) RLS đồng nhất, (b) index theo tenant, (c) không phải JOIN nhiều cấp để biết chủ sở hữu.

Danh sách 28 bảng cần thêm `tenant_id`:
`users, assignments, programs, plos, pis, courses, course_plo, course_outlines, clos, clo_plo, assessments, assessment_clo, lesson_plans, lesson_plan_clo, textbooks, chapters, chapter_clo, questions, exam_matrices, exams, exam_question, documents, extractions, audit_logs, api_keys, lectures, llm_usage, jobs`.

> Bảng `tenants` (và bảng cấu hình nền tảng) **không** có tenant_id.

### 2.3. Index & ràng buộc duy nhất theo tenant
- **Mọi index lọc nóng** đổi sang **composite dẫn đầu bằng tenant_id**, ví dụ:
  - `ix_questions_tenant_course_review (tenant_id, course_id, review_status)`
  - `ix_course_outlines_tenant_course (tenant_id, course_id)`
  - `ix_llm_usage_tenant_created (tenant_id, created_at)`
  - `ix_jobs_tenant_status (tenant_id, status)`
- **Tính duy nhất phải gắn tenant:**
  - `users.email` → unique theo **(tenant_id, email)** (cùng email có thể tồn tại ở 2 trường) — *hoặc* giữ email toàn cục nếu chọn 1 tài khoản dùng nhiều trường (xem §5, cần chốt).
  - `programs.code`, `courses.code` → unique theo (tenant_id, code) nếu cần.
  - Các `UniqueConstraint` hiện có (course_plo, clo_plo, …) bổ sung tenant_id để tránh đụng độ chéo.

### 2.4. Khóa ngoại
Giữ FK hiện tại; bổ sung kiểm tra **nhất quán tenant** (cha–con cùng tenant) — thực thi bằng RLS/trigger hoặc kiểm ở tầng service khi ghi.

---

## 3. Định danh & định tuyến tenant (Tenant Resolution)

### 3.1. Cách xác định tenant của một request
Thứ tự ưu tiên:
1. **Subdomain**: `neu.eduobe.vn`, `ftu.eduobe.vn` → tách `code` từ host. (Khuyến nghị mặc định)
2. **Tên miền riêng** (custom domain) ánh xạ trong `tenants.primary_domain` (vd `obe.neu.edu.vn`).
3. **Header** `X-Tenant` (cho API/máy chủ↔máy chủ, testing).
4. **Trong JWT** (`tenant_id`/`tenant_code`) — sau khi đăng nhập, token đã gắn tenant; backend đối chiếu với host để tránh nhầm.

### 3.2. Middleware phân giải tenant (backend)
- Middleware đọc host/header → tra `tenants` (có cache in-memory TTL) → đặt **contextvar `tenant_id`** (mở rộng `app/core/llm_context.py` thành `app/core/tenant_context.py`).
- Nếu không phân giải được → 404 "tenant không tồn tại" (trừ các route nền tảng/health).
- Route công khai (health, login) cần biết tenant để xác thực đúng phạm vi.

### 3.3. Frontend (Next.js)
- Lấy tenant từ **hostname** (subdomain) ở client + server component.
- Branding (logo/tên/màu) nạp theo tenant: endpoint công khai `GET /api/tenant/branding` theo host.
- `NEXT_PUBLIC_API_BASE`: 1 API dùng chung; tenant suy ra từ host (gửi cookie/host) — không cần build riêng mỗi trường.

---

## 4. Cách ly & bảo mật dữ liệu (trọng tâm)

### 4.1. Lớp 1 — Lọc tự động ở tầng ứng dụng
- **Session DB gắn tenant**: `get_db()` đọc contextvar tenant và:
  - Áp **bộ lọc tự động** cho mọi truy vấn ORM bằng SQLAlchemy event/`with_loader_criteria` (global filter theo tenant_id cho mọi model có thuộc tính tenant_id), HOẶC
  - Bắt buộc dùng helper `tenant_query(db, Model)` trả query đã `.filter(Model.tenant_id == current_tenant())`.
  - **Khi ghi (INSERT)**: tự gán `tenant_id = current_tenant()` (SQLAlchemy `before_flush`/default) để service không phải nhớ.
- Rà soát từng router: bỏ truy vấn "trần" (`db.query(...).all()` không tenant). Đây là phần công sức lớn — cần checklist toàn bộ endpoint.

### 4.2. Lớp 2 — Postgres Row-Level Security (RLS) (chặn cuối)
- Bật `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + policy `USING (tenant_id = current_setting('app.tenant_id')::int)` cho mọi bảng có tenant_id.
- Mỗi request/giao dịch: `SET LOCAL app.tenant_id = :tid` ngay sau khi mở transaction (trong `get_db`).
- **Lưu ý pooling**: phải dùng `SET LOCAL` (theo transaction) hoặc reset khi trả connection về pool — tránh "rò" tenant giữa các request dùng chung connection. Cần test kỹ với `pool_size`.
- Tài khoản DB ứng dụng **không** là superuser/owner (RLS không áp cho owner) — tạo role riêng `app_rw` bị ràng buộc RLS; role migrate (`BYPASSRLS`) tách riêng cho Alembic.

### 4.3. Vai trò nền tảng (super-admin) xuyên tenant
- Vai trò mới `platform_admin` (ngoài RBAC trường). Khi thao tác xuyên tenant (báo cáo toàn nền tảng, cấp phát) → dùng kết nối/role có quyền bỏ qua filter, có **audit log riêng**, bắt buộc lý do.
- Tuyệt đối không lộ super-admin cho người dùng cấp trường.

### 4.4. Kiểm soát rò rỉ chéo
- Mọi endpoint nhận `id` (vd `/outlines/{id}`) phải kiểm `obj.tenant_id == current_tenant()` (RLS lo phần này, nhưng vẫn trả 404 thay vì 403 để không lộ tồn tại).
- Test cách ly chéo là hạng mục bắt buộc (xem §11).

---

## 5. Xác thực & định danh người dùng

- **Người dùng thuộc một tenant.** Đăng nhập gắn tenant (suy từ host). JWT chứa `tenant_id`, `role`, `sub`.
- **Tính duy nhất email** — cần chốt (xem §16): 
  - *Phương án 1 (đơn giản):* email unique theo (tenant_id, email) → cùng email dùng ở nhiều trường là 2 tài khoản khác nhau.
  - *Phương án 2 (1 danh tính nhiều trường):* bảng `identities` toàn cục + `memberships(identity_id, tenant_id, role)` → người dùng chuyển tenant bằng "switch workspace". Phức tạp hơn, để sau.
- Backend mọi nơi đối chiếu `token.tenant_id == request.tenant_id` (chống dùng token tenant A trên host tenant B).
- SSO/LDAP theo trường: thiết kế chừa chỗ (cấu hình IdP trong `tenants.settings_json`), triển khai sau.

---

## 6. Cấu hình theo tenant

Lưu trong `tenants.settings_json` (+ bảng phụ nếu lớn):
- **Branding**: logo, tên hiển thị, màu chủ đạo, favicon, footer liên hệ.
- **Locale/ngôn ngữ** mặc định; bật/tắt song ngữ.
- **Feature flags** theo gói (vd: bật/tắt module bài giảng, import, job nền…).
- **Mặc định nghiệp vụ**: cơ cấu đánh giá (10-30-60…), số CLO/tuần mặc định, mẫu đề cương riêng.
- **AI key**: key Claude/OpenAI **riêng của trường** (khuyến nghị, để chi phí về đúng trường) HOẶC dùng key nền tảng + hạn mức (xem §9). Key mã hóa khi lưu (xem §13).

---

## 7. Lưu trữ file (GCS) theo tenant

- **Tiền tố theo tenant**: `gs://<bucket>/t/<tenant_id>/<loại>/<uuid>` — sửa `storage.put_file()` để chèn tenant prefix tự động từ context.
- Khi đọc (`get_bytes`/`local_path`/gói minh chứng): kiểm key thuộc đúng tenant (so khớp prefix với current tenant) → chống đọc chéo.
- Tùy chọn enterprise: **bucket riêng/tenant** + CMEK (khóa mã hóa riêng) cho trường yêu cầu cao.
- Dùng **signed URL** ngắn hạn khi cho tải file thay vì stream qua app (giảm tải + kiểm soát).

---

## 8. Job nền theo tenant

- Bảng `jobs` thêm `tenant_id`. `create_job()` gán tenant từ context.
- `run_job()`/worker (Cloud Tasks) **thiết lập lại tenant context** từ `job.tenant_id` (vì chạy ngoài request HTTP). Payload Cloud Tasks mang `tenant_id` + `job_id`.
- `llm_scope` mở rộng kèm `tenant_id` để usage gắn đúng trường.
- **Công bằng tài nguyên (fairness)**: hàng đợi/giới hạn đồng thời **theo tenant** để 1 trường import lớn không làm nghẽn trường khác (vd semaphore theo tenant, hoặc nhiều queue Cloud Tasks).

---

## 9. Chi phí & hạn mức LLM theo tenant

- `llm_usage` thêm `tenant_id`; mọi ghi nhận gắn tenant.
- **Hạn mức**: chuyển `LLM_DAILY_TOKEN_QUOTA_PER_PROGRAM` → hạn mức **theo tenant** (và tùy chọn theo chương trình trong tenant). Đọc từ `tenants` thay vì biến môi trường toàn cục.
- **Rate limit theo tenant** (chống 1 trường chiếm hết hạn mức gọi nhà cung cấp).
- **Mô hình key AI**: (a) trường dùng key riêng → chi phí về trường, hạn mức tự quản; (b) dùng key nền tảng → nền tảng tính phí lại theo token (metering) phục vụ hóa đơn.
- Dashboard chi phí: trang Admin trường xem **của trường mình**; `platform_admin` xem **toàn nền tảng + theo từng trường** (mở rộng `/api/llm-usage` đã có thành lọc theo tenant).

---

## 10. Cấp phát & vòng đời tenant (Provisioning)

- **Tạo tenant**: API/CLI `platform_admin` tạo `tenants` + seed mặc định (vai trò, admin trường đầu tiên, cấu hình mẫu). Tùy chọn self-serve đăng ký dùng thử.
- **Trạng thái**: `trial` → `active` → `suspended` (ngừng dịch vụ khi hết hạn/nợ phí, chặn đăng nhập trừ admin) → `offboarding`.
- **Offboarding/Export**: xuất toàn bộ dữ liệu 1 trường (zip JSON + file) trước khi xóa; **xóa dữ liệu** (hard-delete theo tenant_id) khi kết thúc hợp đồng.
- **Backup/restore theo tenant**: dù chung DB, cần kịch bản trích/khôi phục theo tenant_id (logical export) phục vụ sự cố 1 trường.
- **Domain/DNS**: wildcard `*.eduobe.vn` + chứng chỉ; custom domain: hướng dẫn CNAME + cấp cert tự động.

---

## 11. Chiến lược kiểm thử (bắt buộc cho multi-tenant)

- **Test cách ly chéo (ưu tiên cao nhất)**: tạo tenant A & B; xác minh người dùng A **không** đọc/sửa/xóa được mọi tài nguyên của B trên mọi endpoint (đề cương, câu hỏi, file, job, usage…). Trả 404.
- **Test RLS** ở tầng DB: với `app.tenant_id` set, truy vấn chỉ thấy hàng đúng tenant; không set → không thấy gì.
- **Test gán tenant tự động** khi ghi (INSERT không truyền tenant vẫn đúng).
- **Test resolution**: subdomain/custom domain/header → đúng tenant; token tenant A trên host B bị từ chối.
- **Test fixtures đa tenant** + hồi quy toàn bộ test hiện có (chạy trong 1 tenant mặc định).
- **Test job/worker**: job tenant B chạy với context tenant B; usage ghi đúng tenant.
- **Pen-test/threat-model** cách ly trước khi mở bán.

---

## 12. Quan trắc & vận hành (Observability)

- **Log/metrics gắn `tenant_id`** ở mọi log nghiệp vụ (structured logging) → lọc sự cố theo trường.
- Dashboard theo tenant: số người dùng hoạt động, job, lỗi, chi phí AI, dung lượng GCS.
- Cảnh báo: tenant vượt hạn mức, tỉ lệ lỗi cao, job treo.
- Trang **platform_admin**: danh sách tenant, trạng thái, mức dùng, chi phí; thao tác suspend/extend.

---

## 13. Bảo mật & tuân thủ

- **Mã hóa API key AI của tenant khi lưu** (envelope encryption qua Cloud KMS thay vì lưu thô như hiện tại) — áp cho cả key hiện hành.
- Nguyên tắc least-privilege role DB (RLS), tách role migrate.
- Audit log gắn tenant + actor; bất biến (append-only).
- Cách ly secret/khóa theo tenant; không log key.
- Chính sách lưu trữ & xóa dữ liệu theo hợp đồng (data residency nếu cần → cân nhắc DB-per-tenant cho trường đặc thù).

---

## 14. Tác động Frontend

- Suy tenant từ host; nạp **branding** động; hiển thị tên/logo trường.
- Màn hình **platform_admin** (mới): quản lý tenant, theo dõi toàn nền tảng.
- Màn hình Admin trường: thêm cấu hình branding, key AI, hạn mức (trong phạm vi tenant).
- Đảm bảo mọi lời gọi API đi kèm ngữ cảnh tenant (cookie/host); xử lý lỗi "tenant bị treo/he hết hạn".

---

## 15. Lộ trình triển khai theo pha (giảm rủi ro, không gãy bản hiện tại)

| Pha | Nội dung | Kết quả |
|---|---|---|
| **C0 — Nền tảng dữ liệu** | Tạo bảng `tenants`; thêm `tenant_id` (nullable) vào 28 bảng; tạo **tenant mặc định**; backfill toàn bộ dữ liệu hiện có về tenant mặc định; thêm composite index theo tenant | DB sẵn sàng, app chạy y như cũ |
| **C1 — Ngữ cảnh & lọc ứng dụng** | `tenant_context` + middleware phân giải (mặc định = tenant mặc định); auto-filter & auto-set tenant khi ghi; rà toàn bộ endpoint | Cách ly ở tầng app; vẫn 1 tenant |
| **C2 — Siết chặt + RLS** | Đặt `tenant_id` NOT NULL; bật RLS + `SET LOCAL` trong `get_db`; role DB least-privilege; test cách ly chéo | Cách ly 2 lớp, an toàn |
| **C3 — Định tuyến & onboarding** | Subdomain/custom domain; branding theo tenant; API + UI cấp phát tenant; vai trò `platform_admin` | Phục vụ nhiều trường thật |
| **C4 — Cấu hình/Chi phí/Hạn mức theo tenant** | Key AI theo tenant (mã hóa KMS), hạn mức & rate limit theo tenant, fairness job, dashboard chi phí theo tenant | Vận hành & tính phí theo trường |
| **C5 — Vận hành & tuân thủ** | Export/offboarding, backup theo tenant, quan trắc gắn tenant, pen-test cách ly, load test đa tenant | Sẵn sàng thương mại |

> Mỗi pha **độc lập deploy được** và giữ tương thích ngược (single-tenant hiện tại = "tenant mặc định").

---

## 16. Quyết định đã CHỐT (2026-06-07)

1. **Định tuyến**: ✅ **Subdomain `*.eduobe.vn`** (mỗi trường một subdomain theo `tenants.code`).
2. **Email người dùng**: ✅ **Duy nhất theo tenant** — unique `(tenant_id, email)`.
3. **Key AI**: ✅ **Mỗi trường tự nạp API key** → chi phí về đúng trường; không dùng key chung.
4. **RLS**: ✅ **Bật RLS Postgres** (cách ly 2 lớp: app filter + RLS).
5. **Mức cách ly**: ✅ **Shared-schema cho tất cả** (không lai DB-per-tenant).
6. **Mã hóa key**: ➜ **Để ở C4** (giữ cách lưu hiện tại ở C0–C2 cho gọn; C4 bổ sung mã hóa khi hoàn thiện quản lý key theo tenant).
7. **Billing**: ✅ **Theo thời gian sử dụng** — mỗi tenant có `valid_until` (mặc định +365 ngày). Hết hạn → **chặn sử dụng** (trừ Super-Admin); sau khi trường thanh toán, **Super-Admin bật lại + gia hạn** (`is_enabled` + `valid_until`). Chưa tích hợp cổng thanh toán tự động.

### Tiến độ thực thi
- ✅ **C0 — Nền tảng dữ liệu**: bảng `tenants` (kèm `is_enabled`, `activated_at`, `valid_until`), thêm `tenant_id` nullable + index cho cả 28 bảng, tạo tenant mặc định, backfill toàn bộ dữ liệu cũ. Migration `9c3e5a7b1d2f`. **Không đổi hành vi app.**
- ✅ **C1 — Cô lập dữ liệu ở tầng ứng dụng** (`app/core/tenant.py`): gắn tenant vào `Session.info` từ user đã xác thực; **auto-filter** mọi SELECT (`do_orm_execute` + `with_loader_criteria` biểu thức trực tiếp — tránh bẫy lambda-caching) và **auto-set** `tenant_id` khi ghi (`before_flush`); JWT mang `tenant_id`; tra cứu user lúc đăng nhập dùng `skip_tenant`; job nền set tenant từ `job.tenant_id`. Khi chưa có tenant (test/cũ) lớp tự tắt. **Có test cô lập chéo A↔B.**
- ✅ **C2 — Siết chặt**:
  - **Seed** tạo/gắn tenant mặc định cho mọi dữ liệu; **fallback tenant mặc định khi GHI ngoài request** (tránh `tenant_id` NULL) — cache id tenant mặc định lúc khởi động.
  - **create_user** kế thừa tenant của admin (auto-set) + kiểm tra trùng email theo tenant.
  - **Email duy nhất theo `(tenant_id, email)`** (model + migration).
  - **NOT NULL `tenant_id`** và **Row-Level Security (RLS)** — *chỉ PostgreSQL* (migration `a1f2e3d4c5b6`, guard theo dialect; no-op trên SQLite). RLS policy "permissive-when-unset" + `SET LOCAL app.tenant_id` (qua `set_session_tenant` + listener `after_begin`) → chặn chéo ở tầng DB khi đã xác thực, không phá luồng đăng nhập/migration.
  - LLM usage gắn `tenant_id` (qua `llm_scope`).
  - **Tests**: kế thừa tenant + email theo tenant + fallback ghi (61 passed).
  - ⚠️ *Cần kiểm thử RLS/NOT NULL trên Postgres staging* (môi trường dev hiện là SQLite nên 2 mục này là no-op khi test).
  - ⚠️ *Gap tạm thời*: đăng nhập đang tra theo email toàn cục (`.first()`); khi 2 trường trùng email sẽ chưa phân biệt — **sẽ xử lý ở C3** (suy tenant theo subdomain trước khi tra user).
- ⏳ C3 → C5: theo §15.

---

## 17. Rủi ro & giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Rò rỉ dữ liệu chéo tenant | Nghiêm trọng | 2 lớp (auto-filter + RLS); test cách ly bắt buộc; trả 404; review từng endpoint |
| Quên filter ở endpoint mới | Cao | Auto-filter mặc định (mọi query phải đi qua session tenant-aware); lint/CI rule; test |
| Rò tenant qua connection pool (RLS/SET) | Cao | `SET LOCAL` theo transaction; test với pool nhỏ; reset on checkin |
| Migration backfill sai/khối lượng lớn | Trung bình | Backfill idempotent theo lô; chạy ngoài giờ; kiểm đếm trước/sau |
| Noisy neighbor (1 trường ngốn tài nguyên) | Trung bình | Hạn mức + rate limit + fairness job theo tenant |
| Quản lý khóa AI nhiều trường | Trung bình | Mã hóa KMS; xoay khóa; không log |
| Hiệu năng do thêm cột/điều kiện | Thấp | Composite index dẫn đầu tenant_id (đã tính ở §2.3) |

---

## 18. Ước lượng công sức (định hướng)

| Pha | Ước lượng |
|---|---|
| C0 Nền tảng dữ liệu + backfill | 3–5 ngày |
| C1 Ngữ cảnh + auto-filter + rà endpoint | 5–8 ngày (rộng do quét toàn bộ router) |
| C2 RLS + role DB + test cách ly | 4–6 ngày |
| C3 Định tuyến + onboarding + branding + platform_admin | 5–8 ngày |
| C4 Key/hạn mức/chi phí/fairness theo tenant | 4–6 ngày |
| C5 Export/backup/quan trắc/pen-test/load test | 4–6 ngày |
| **Tổng** | **~5–7 tuần** (1 kỹ sư), có thể song song một phần |

---

## 19. Tiêu chí hoàn thành (Definition of Done)

- Một codebase + một hạ tầng phục vụ ≥ 2 trường thật, **cách ly dữ liệu đã được kiểm thử & pen-test**.
- Tự phục vụ/cấp phát tenant; branding & cấu hình theo trường; key AI + hạn mức + chi phí theo trường.
- Toàn bộ test hồi quy xanh + bộ test cách ly chéo xanh; RLS bật trên prod.
- Quan trắc & cảnh báo gắn tenant; quy trình export/offboarding/backup theo tenant.
- Tài liệu vận hành: tạo trường mới, gắn domain, cấu hình key, đình chỉ/khôi phục.
