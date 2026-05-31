import io
import json
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import AuditLog, Document, Program, Role, User
from app.services.reports import program_coverage_report

router = APIRouter(prefix="/api", tags=["reports"])
QA = require_roles(Role.QA, Role.PROGRAM_MANAGER)


@router.get("/documents")
def list_documents(
    type: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Kho minh chứng: liệt kê tài liệu gốc (SPEC 4.7), lọc theo loại."""
    q = db.query(Document)
    if type:
        q = q.filter(Document.type == type)
    rows = q.order_by(Document.id.desc()).all()
    return [
        {
            "id": d.id, "type": d.type, "original_name": d.original_name,
            "mime": d.mime, "uploaded_by": d.uploaded_by,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "text_length": len(d.extracted_text or ""),
        }
        for d in rows
    ]


@router.get("/programs/{program_id}/coverage-report")
def coverage_report(program_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Báo cáo phủ chuẩn PLO→PI→CLO→đánh giá (SPEC 4.7)."""
    if not db.get(Program, program_id):
        raise HTTPException(404, "Không tìm thấy CTĐT")
    return program_coverage_report(db, program_id)


@router.get("/audit-logs")
def audit_logs(
    entity: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(QA),
):
    """Nhật ký kiểm định: ai – làm gì – khi nào (SPEC 4.7)."""
    q = db.query(AuditLog)
    if entity:
        q = q.filter(AuditLog.entity == entity)
    rows = q.order_by(AuditLog.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id, "user_id": r.user_id, "entity": r.entity, "entity_id": r.entity_id,
            "action": r.action, "diff": r.diff_json, "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/programs/{program_id}/evidence-package")
def evidence_package(program_id: int, db: Session = Depends(get_db), _: User = Depends(QA)):
    """Xuất gói minh chứng (zip) cho AUN-QA: báo cáo phủ chuẩn + file gốc (SPEC 4.7)."""
    prog = db.get(Program, program_id)
    if not prog:
        raise HTTPException(404, "Không tìm thấy CTĐT")
    report = program_coverage_report(db, program_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("coverage_report.json", json.dumps(report, ensure_ascii=False, indent=2))
        z.writestr(
            "program.json",
            json.dumps(
                {"name": prog.name, "code": prog.code, "year": prog.year, "faculty": prog.faculty},
                ensure_ascii=False, indent=2,
            ),
        )
        if prog.source_document_id:
            doc = db.get(Document, prog.source_document_id)
            if doc and doc.extracted_text:
                z.writestr("source_document.txt", doc.extracted_text)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=evidence_{prog.code or program_id}.zip"},
    )
