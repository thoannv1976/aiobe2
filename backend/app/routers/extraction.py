import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import (
    Course,
    CoursePlo,
    Document,
    Extraction,
    Pi,
    Plo,
    Program,
    Role,
    User,
)
from app.schemas.extraction import ExtractionPayload
from app.services.audit import log_action
from app.services.extraction import call_llm_extract, extract_text_from_file

router = APIRouter(prefix="/api", tags=["extraction"])
MANAGER = require_roles(Role.PROGRAM_MANAGER, Role.LECTURER)


from fastapi import Form  # noqa: E402

# Các loại tài liệu hỗ trợ (SPEC 4.1, 4.3).
DOC_TYPES = {"program_proposal", "outline_template", "aunqa_standard"}


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    doc_type: str = Form("program_proposal"),
    db: Session = Depends(get_db),
    user: User = Depends(MANAGER),
):
    """Upload tài liệu (PDF/DOCX/TXT). Lưu file gốc làm minh chứng (SPEC 4.1).

    doc_type: program_proposal (đề án mở ngành) | outline_template (mẫu đề cương)
    | aunqa_standard (tài liệu chuẩn AUN-QA).
    """
    if doc_type not in DOC_TYPES:
        doc_type = "program_proposal"
    os.makedirs(settings.storage_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    saved = os.path.join(settings.storage_dir, f"{uuid.uuid4().hex}{ext}")
    with open(saved, "wb") as f:
        f.write(await file.read())
    text = ""
    try:
        text = extract_text_from_file(saved, file.content_type)
    except Exception as e:  # noqa: BLE001
        text = f"[Không trích được văn bản: {e}]"
    doc = Document(
        type=doc_type, file_path=saved, mime=file.content_type,
        uploaded_by=user.id, original_name=file.filename, extracted_text=text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    log_action(db, user.id, "document", doc.id, "upload", {"doc_type": doc_type})
    return {"document_id": doc.id, "original_name": doc.original_name, "type": doc.type, "text_length": len(text)}


@router.post("/documents/{doc_id}/extract")
def run_extraction(doc_id: int, db: Session = Depends(get_db), user: User = Depends(MANAGER)):
    """Gọi LLM trích xuất có cấu trúc -> tạo bản nháp chờ con người xác nhận."""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    try:
        payload = call_llm_extract(doc.extracted_text or "")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Trích xuất thất bại: {e}")
    obj = Extraction(document_id=doc_id, payload_json=payload.model_dump(), status="pending")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "extraction", obj.id, "extract")
    return {"extraction_id": obj.id, "payload": obj.payload_json, "status": obj.status}


@router.get("/documents/{doc_id}/text")
def get_text(doc_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    return {"document_id": doc_id, "text": doc.extracted_text}


@router.get("/extractions/{ext_id}")
def get_extraction(ext_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    obj = db.get(Extraction, ext_id)
    if not obj:
        raise HTTPException(404, "Không tìm thấy bản trích xuất")
    return {"id": obj.id, "document_id": obj.document_id, "payload": obj.payload_json, "status": obj.status}


@router.post("/extractions/{ext_id}/confirm")
def confirm_extraction(
    ext_id: int,
    payload: ExtractionPayload,
    db: Session = Depends(get_db),
    user: User = Depends(MANAGER),
):
    """Con người rà soát & xác nhận -> ghi vào CSDL (SPEC 4.1, human-in-the-loop).

    Nhận lại payload (đã chỉnh sửa) từ giao diện rà soát thay vì dùng bản gốc.
    """
    obj = db.get(Extraction, ext_id)
    if not obj:
        raise HTTPException(404, "Không tìm thấy bản trích xuất")
    if obj.status == "confirmed":
        raise HTTPException(400, "Bản trích xuất đã được xác nhận")

    prog = Program(
        name=payload.program.name or "(chưa đặt tên)",
        code=payload.program.code, level=payload.program.level,
        year=payload.program.year or None, faculty=payload.program.faculty,
        source_document_id=obj.document_id,
    )
    db.add(prog)
    db.flush()

    plo_by_code: dict[str, Plo] = {}
    for p in payload.plos:
        plo = Plo(
            program_id=prog.id, code=p.code, description=p.description,
            category=p.category or None, bloom_level=p.bloom_level or None,
        )
        db.add(plo)
        db.flush()
        plo_by_code[p.code] = plo

    for pi in payload.pis:
        plo = plo_by_code.get(pi.plo_code)
        if plo:
            db.add(Pi(plo_id=plo.id, code=pi.code, description=pi.description))

    course_by_code: dict[str, Course] = {}
    for c in payload.courses:
        course = Course(
            program_id=prog.id, code=c.code, name=c.name,
            credits=c.credits or 0, semester=c.semester or None,
            type=c.type or "core", prerequisites_json=c.prerequisites,
        )
        db.add(course)
        db.flush()
        course_by_code[c.code] = course

    for cp in payload.course_plo_matrix:
        course = course_by_code.get(cp.course_code)
        plo = plo_by_code.get(cp.plo_code)
        if course and plo and cp.level:
            db.add(CoursePlo(course_id=course.id, plo_id=plo.id, level=cp.level))

    obj.status = "confirmed"
    db.commit()
    log_action(db, user.id, "extraction", ext_id, "confirm", {"program_id": prog.id})
    return {"program_id": prog.id, "plos": len(payload.plos), "courses": len(payload.courses)}
