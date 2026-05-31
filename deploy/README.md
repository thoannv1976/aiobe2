# Deploy lên Google Cloud Run

Triển khai **backend (FastAPI)** + **frontend (Next.js)** lên Cloud Run, dùng **Cloud SQL Postgres**.
Project `aiobe2`, region `asia-southeast1`.

## Yêu cầu trước khi chạy
- Cài [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`).
- Đăng nhập & có quyền trên project `aiobe2` (Owner hoặc Editor + Cloud Run/SQL/Secret/Artifact admin):
  ```bash
  gcloud auth login
  gcloud config set project aiobe2
  ```
- Đã bật billing cho project (Cloud SQL & Cloud Run yêu cầu).
- (Tùy chọn) Có `ANTHROPIC_API_KEY` để bật module trích xuất AI.

## Chạy tự động (khuyến nghị)
Từ **thư mục gốc repo**:
```bash
export ANTHROPIC_API_KEY=sk-ant-...   # tùy chọn
./deploy/deploy.sh
```
Script `deploy/deploy.sh` thực hiện toàn bộ, **idempotent** (chạy lại an toàn):

| Bước | Việc làm |
|---|---|
| 0 | `gcloud config set project` + bật API (run, artifactregistry, cloudbuild, sqladmin, secretmanager) |
| 1 | Tạo Artifact Registry repo `obe` |
| 2 | Tạo Cloud SQL Postgres `obe-pg` + database `obe` + user `obe` (mật khẩu sinh ngẫu nhiên, lưu Secret Manager) |
| 3 | Ghi secrets: `obe-database-url`, `obe-jwt-secret`, `anthropic-api-key`; cấp `cloudsql.client` + `secretAccessor` cho SA runtime |
| 4 | Build & push image backend (Cloud Build) |
| 5 | **Cloud Run Job** `obe-migrate`: `alembic upgrade head && python -m app.seed` |
| 6 | Deploy service `obe-api` (gắn Cloud SQL, secrets) |
| 7 | Lấy URL backend → build frontend với `NEXT_PUBLIC_API_BASE=<url-backend>` |
| 8 | Deploy service `obe-web` |
| 9 | Siết `CORS_ORIGINS` của backend = URL frontend |
| 10 | In URL + health check |

## Vì sao có các thay đổi này (so với bản local/Docker Compose)
- **`$PORT`**: Cloud Run cấp cổng động (8080). Dockerfile backend/frontend đã đổi để nghe `$PORT`.
- **Migrate/seed tách khỏi CMD**: chạy bằng Cloud Run Job một lần, tránh chạy lại mỗi cold-start. App chỉ `create_all` khi dùng SQLite; trên Postgres để Alembic quản schema.
- **NEXT_PUBLIC_API_BASE bake lúc build**: phải deploy backend trước để lấy URL, rồi mới build frontend → đó là lý do thứ tự bước 6→7→8.
- **Cloud SQL qua unix socket**: `DATABASE_URL=postgresql+psycopg2://user:pass@/obe?host=/cloudsql/<conn>` + `--add-cloudsql-instances`.

## Tùy biến
Đặt biến môi trường trước khi chạy để đổi mặc định, ví dụ:
```bash
PROJECT=aiobe2 REGION=asia-southeast1 SQL_TIER=db-g1-small ./deploy/deploy.sh
```
Các biến: `PROJECT REGION REPO SQL_INSTANCE SQL_TIER DB_NAME DB_USER API_SERVICE WEB_SERVICE MIGRATE_JOB ANTHROPIC_MODEL`.

## Cập nhật lại (redeploy code mới)
Chạy lại `./deploy/deploy.sh` — sẽ build image mới, chạy lại migrate job (seed idempotent), và cập nhật service.

## Chi phí & dọn dẹp
- Cloud SQL `db-f1-micro` chạy 24/7 là khoản tốn chính (~vài USD/tháng). Cloud Run scale-to-zero gần như miễn phí khi không có traffic.
- Xóa toàn bộ khi không dùng:
  ```bash
  gcloud run services delete obe-api obe-web --region=asia-southeast1
  gcloud run jobs delete obe-migrate --region=asia-southeast1
  gcloud sql instances delete obe-pg
  gcloud artifacts repositories delete obe --location=asia-southeast1
  ```

## Lưu ý
- File upload (module trích xuất) ghi vào `./storage` trong container — **ephemeral** trên Cloud Run. Để bền vững nên chuyển sang GCS (chưa làm; xem "Hướng phát triển tiếp" ở README gốc).
- `--allow-unauthenticated` để public. Nếu muốn nội bộ, bỏ cờ này và cấu hình IAM/IAP.
