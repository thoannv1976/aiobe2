"""Kiểm thử cô lập RLS trên PostgreSQL staging (Nhóm C / C5 — pen-test).

RLS chỉ hoạt động trên Postgres; bộ test pytest dùng SQLite nên là no-op. Script này chạy
trực tiếp trên DB Postgres đã `alembic upgrade head` để xác minh chính sách RLS hoạt động:

    DATABASE_URL=postgresql+psycopg2://user:pass@host/db python -m scripts.verify_rls

Kịch bản:
  1) Tạo 2 tenant + 1 program mỗi tenant (bằng app.tenant_id phù hợp).
  2) SET app.tenant_id = A → chỉ thấy program của A; = B → chỉ thấy của B.
  3) Thử ghi sai tenant (WITH CHECK) → bị chặn.
Thoát mã 0 nếu cô lập đúng, !=0 nếu phát hiện rò rỉ.
"""
from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.config import settings


def main() -> int:
    if not settings.database_url.startswith("postgresql"):
        print("⚠ Script này chỉ dành cho PostgreSQL. DATABASE_URL hiện tại:", settings.database_url)
        return 2
    eng = create_engine(settings.database_url)
    ok = True
    with eng.begin() as c:
        # Tạo 2 tenant kiểm thử.
        c.execute(text("INSERT INTO tenants (code,name,status,plan,is_enabled,created_at,updated_at) "
                       "VALUES ('rlsa','RLS A','active','standard',true,now(),now()), "
                       "('rlsb','RLS B','active','standard',true,now(),now()) "
                       "ON CONFLICT (code) DO NOTHING"))
        a = c.execute(text("SELECT id FROM tenants WHERE code='rlsa'")).scalar()
        b = c.execute(text("SELECT id FROM tenants WHERE code='rlsb'")).scalar()

        # Ghi 1 program cho mỗi tenant (đặt app.tenant_id đúng để qua WITH CHECK).
        c.execute(text("SET LOCAL app.tenant_id = :t").bindparams(t=a))
        c.execute(text("INSERT INTO programs (tenant_id,name,code,is_deleted,created_at) "
                       "VALUES (:t,'PA','RLSPA',false,now())").bindparams(t=a))
        c.execute(text("SET LOCAL app.tenant_id = :t").bindparams(t=b))
        c.execute(text("INSERT INTO programs (tenant_id,name,code,is_deleted,created_at) "
                       "VALUES (:t,'PB','RLSPB',false,now())").bindparams(t=b))

    with eng.connect() as c:
        c.execute(text("SET app.tenant_id = :t").bindparams(t=a))
        rows_a = {r[0] for r in c.execute(text("SELECT code FROM programs")).all()}
        c.execute(text("SET app.tenant_id = :t").bindparams(t=b))
        rows_b = {r[0] for r in c.execute(text("SELECT code FROM programs")).all()}

    print("Tenant A thấy:", rows_a)
    print("Tenant B thấy:", rows_b)
    if "RLSPB" in rows_a or "RLSPA" in rows_b:
        print("❌ RÒ RỈ: một tenant thấy dữ liệu tenant khác!")
        ok = False
    if "RLSPA" not in rows_a or "RLSPB" not in rows_b:
        print("❌ RLS chặn nhầm dữ liệu hợp lệ của chính tenant.")
        ok = False

    # Thử ghi sai tenant → WITH CHECK phải chặn.
    try:
        with eng.begin() as c:
            c.execute(text("SET LOCAL app.tenant_id = :t").bindparams(t=a))
            c.execute(text("INSERT INTO programs (tenant_id,name,code,is_deleted,created_at) "
                           "VALUES (:b,'X','RLSX',false,now())").bindparams(b=b))
        print("❌ WITH CHECK KHÔNG chặn ghi sai tenant!")
        ok = False
    except Exception:
        print("✔ WITH CHECK chặn ghi sai tenant (đúng).")

    print("KẾT QUẢ:", "ĐẠT ✅" if ok else "KHÔNG ĐẠT ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
