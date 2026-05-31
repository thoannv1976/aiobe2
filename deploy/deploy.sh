#!/usr/bin/env bash
#
# Deploy hệ thống OBE/AUN-QA lên Google Cloud Run (backend + frontend) với Cloud SQL Postgres.
# Chạy từ THƯ MỤC GỐC repo, bằng tài khoản gcloud đã đăng nhập:
#
#     gcloud auth login          # (nếu chưa)
#     export ANTHROPIC_API_KEY=sk-ant-...   # (tùy chọn, để bật trích xuất AI)
#     ./deploy/deploy.sh
#
# Script idempotent: chạy lại an toàn (bỏ qua tài nguyên đã tồn tại).
set -euo pipefail

# ----------------------------- Cấu hình -----------------------------
PROJECT="${PROJECT:-aiobe2}"
REGION="${REGION:-asia-southeast1}"
REPO="${REPO:-obe}"                       # Artifact Registry repo
SQL_INSTANCE="${SQL_INSTANCE:-obe-pg}"    # Cloud SQL instance
SQL_TIER="${SQL_TIER:-db-f1-micro}"
DB_NAME="${DB_NAME:-obe}"
DB_USER="${DB_USER:-obe}"
API_SERVICE="${API_SERVICE:-obe-api}"
WEB_SERVICE="${WEB_SERVICE:-obe-web}"
MIGRATE_JOB="${MIGRATE_JOB:-obe-migrate}"
ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-4-8}"

AR_HOST="${REGION}-docker.pkg.dev"
API_IMAGE="${AR_HOST}/${PROJECT}/${REPO}/api:latest"
WEB_IMAGE="${AR_HOST}/${PROJECT}/${REPO}/web:latest"
CONN_NAME="${PROJECT}:${REGION}:${SQL_INSTANCE}"

say() { echo -e "\n\033[1;36m▶ $*\033[0m"; }

# ---------------------- 0. Project & APIs ----------------------
say "Đặt project = ${PROJECT} và bật các API cần thiết"
gcloud config set project "${PROJECT}"
gcloud services enable \
  run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT}" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# ---------------------- 1. Artifact Registry ----------------------
say "Tạo Artifact Registry repo '${REPO}' (nếu chưa có)"
gcloud artifacts repositories describe "${REPO}" --location="${REGION}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker --location="${REGION}" \
    --description="OBE/AUN-QA images"

# ---------------------- 2. Cloud SQL ----------------------
say "Tạo Cloud SQL Postgres instance '${SQL_INSTANCE}' (có thể mất vài phút)"
if ! gcloud sql instances describe "${SQL_INSTANCE}" >/dev/null 2>&1; then
  gcloud sql instances create "${SQL_INSTANCE}" \
    --database-version=POSTGRES_16 --tier="${SQL_TIER}" --edition=ENTERPRISE \
    --region="${REGION}" --storage-size=10GB --storage-auto-increase
fi

say "Tạo database '${DB_NAME}' và user '${DB_USER}'"
gcloud sql databases describe "${DB_NAME}" --instance="${SQL_INSTANCE}" >/dev/null 2>&1 || \
  gcloud sql databases create "${DB_NAME}" --instance="${SQL_INSTANCE}"

# Sinh mật khẩu DB nếu chưa có secret; nếu có rồi thì tái sử dụng.
if gcloud secrets describe obe-db-password >/dev/null 2>&1; then
  DB_PASS="$(gcloud secrets versions access latest --secret=obe-db-password)"
else
  DB_PASS="$(openssl rand -hex 24)"
  printf '%s' "${DB_PASS}" | gcloud secrets create obe-db-password --data-file=-
fi
if gcloud sql users list --instance="${SQL_INSTANCE}" --format='value(name)' | grep -qx "${DB_USER}"; then
  gcloud sql users set-password "${DB_USER}" --instance="${SQL_INSTANCE}" --password="${DB_PASS}"
else
  gcloud sql users create "${DB_USER}" --instance="${SQL_INSTANCE}" --password="${DB_PASS}"
fi

# ---------------------- 3. Secrets ----------------------
# Kết nối qua unix socket Cloud SQL: host=/cloudsql/<conn>
DATABASE_URL="postgresql+psycopg2://${DB_USER}:${DB_PASS}@/${DB_NAME}?host=/cloudsql/${CONN_NAME}"

upsert_secret() {  # $1=name  $2=value
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    printf '%s' "$2" | gcloud secrets versions add "$1" --data-file=-
  else
    printf '%s' "$2" | gcloud secrets create "$1" --data-file=-
  fi
}

say "Ghi secrets (DATABASE_URL, JWT_SECRET, ANTHROPIC_API_KEY)"
upsert_secret obe-database-url "${DATABASE_URL}"
if ! gcloud secrets describe obe-jwt-secret >/dev/null 2>&1; then
  upsert_secret obe-jwt-secret "$(openssl rand -hex 32)"
fi
upsert_secret anthropic-api-key "${ANTHROPIC_API_KEY:-}"

say "Cấp quyền cho service account runtime (${RUNTIME_SA})"
for ROLE in roles/cloudsql.client roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT}" \
    --member="serviceAccount:${RUNTIME_SA}" --role="${ROLE}" --condition=None >/dev/null
done

# ---------------------- 4. Build backend ----------------------
say "Build & push image backend"
gcloud builds submit --config deploy/cloudbuild.backend.yaml \
  --substitutions _IMAGE="${API_IMAGE}" backend

# ---------------------- 5. Migrate + seed (Cloud Run Job) ----------------------
say "Chạy migrate + seed qua Cloud Run Job"
gcloud run jobs deploy "${MIGRATE_JOB}" \
  --image="${API_IMAGE}" --region="${REGION}" \
  --set-cloudsql-instances="${CONN_NAME}" \
  --set-secrets="DATABASE_URL=obe-database-url:latest" \
  --command="sh" \
  --args="-c,alembic upgrade head && python -m app.seed"
gcloud run jobs execute "${MIGRATE_JOB}" --region="${REGION}" --wait

# ---------------------- 6. Deploy backend service ----------------------
say "Deploy backend service '${API_SERVICE}'"
gcloud run deploy "${API_SERVICE}" \
  --image="${API_IMAGE}" --region="${REGION}" \
  --platform=managed --allow-unauthenticated \
  --add-cloudsql-instances="${CONN_NAME}" \
  --set-secrets="DATABASE_URL=obe-database-url:latest,JWT_SECRET=obe-jwt-secret:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest" \
  --set-env-vars="ANTHROPIC_MODEL=${ANTHROPIC_MODEL},CORS_ORIGINS=*" \
  --timeout=900 --memory=1Gi --cpu=1

API_URL="$(gcloud run services describe "${API_SERVICE}" --region="${REGION}" --format='value(status.url)')"
say "Backend URL: ${API_URL}"

# ---------------------- 7. Build frontend (bake API URL) ----------------------
say "Build & push image frontend (NEXT_PUBLIC_API_BASE=${API_URL})"
gcloud builds submit --config deploy/cloudbuild.frontend.yaml \
  --substitutions _IMAGE="${WEB_IMAGE}",_API_BASE="${API_URL}" frontend

# ---------------------- 8. Deploy frontend service ----------------------
say "Deploy frontend service '${WEB_SERVICE}'"
gcloud run deploy "${WEB_SERVICE}" \
  --image="${WEB_IMAGE}" --region="${REGION}" \
  --platform=managed --allow-unauthenticated

WEB_URL="$(gcloud run services describe "${WEB_SERVICE}" --region="${REGION}" --format='value(status.url)')"

# ---------------------- 9. Siết CORS về đúng domain frontend ----------------------
say "Cập nhật CORS_ORIGINS của backend = ${WEB_URL}"
gcloud run services update "${API_SERVICE}" --region="${REGION}" \
  --update-env-vars="CORS_ORIGINS=${WEB_URL}"

# ---------------------- 10. Kết quả + smoke test ----------------------
say "Hoàn tất!"
echo "  Backend : ${API_URL}"
echo "  Frontend: ${WEB_URL}"
echo
echo "Health check:"
curl -s "${API_URL}/api/health" || true
echo
echo "Đăng nhập thử: manager@obe.vn / manager123"
