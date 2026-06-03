"""Sinh đề cương học phần bằng AI theo chuẩn OBE/AUN-QA (SPEC 4.3).

Căn cứ: thông tin học phần + CTĐT + PLO + PI + ma trận Học phần×PLO của học phần,
kèm (tùy chọn) mẫu đề cương và tài liệu chuẩn AUN-QA do người dùng upload.
Output JSON được validate bằng Pydantic (GeneratedOutline) — human-in-the-loop.
"""
from __future__ import annotations

import json

from app.schemas.outline_gen import GeneratedOutline
from app.services.llm import llm_complete

OUTLINE_SYSTEM_PROMPT = """Bạn là chuyên gia thiết kế chương trình đào tạo theo chuẩn OBE \
(Outcome-Based Education) và kiểm định AUN-QA. Nhiệm vụ: soạn ĐỀ CƯƠNG HỌC PHẦN tiếng Việt \
bảo đảm "constructive alignment" (nhất quán dọc CLO ↔ dạy-học ↔ đánh giá).

Yêu cầu bắt buộc về chất lượng (AUN-QA):
- Soạn KHOẢNG {num_clos} CLO (chuẩn đầu ra học phần), không quá ít cũng không quá nhiều.
- CLO viết theo thang Bloom, đo lường được, MỖI CLO bắt đầu bằng một động từ Bloom. \
{bloom_style}
- CLO phủ cân đối kiến thức/kỹ năng/thái độ phù hợp tính chất học phần.
- MỖI CLO phải ánh xạ tới ít nhất một PLO của chương trình (dùng đúng mã PLO được cung cấp), \
kèm mức đóng góp I (Introduce) / R (Reinforce) / M (Master) hợp lý với vai trò học phần.
- MỖI CLO phải được phủ bởi ít nhất một cấu phần đánh giá (constructive alignment).
- {assessment_rule}
- Tổng trọng số các cấu phần đánh giá BẰNG ĐÚNG 100.
- MỖI cấu phần đánh giá phải kèm RUBRIC: 2–4 tiêu chí chấm điểm, mỗi tiêu chí có trọng số (%) \
trong cấu phần (tổng các tiêu chí của một cấu phần = 100) và mô tả 3–4 MỨC chất lượng \
(ví dụ Giỏi/Khá/Đạt/Chưa đạt) cụ thể, đo lường được.
- Kế hoạch giảng dạy trải {num_weeks} tuần, mỗi tuần một chủ đề gắn với (các) CLO liên quan; \
toàn bộ CLO đều phải xuất hiện trong kế hoạch giảng dạy.
- Phương pháp dạy-học đa dạng, phù hợp để đạt CLO (thuyết giảng, thảo luận, thực hành, dự án…).

Chỉ trả về DUY NHẤT một JSON hợp lệ (không markdown, không văn bản thừa) theo schema:
{{
  "description": "mô tả học phần",
  "teaching_methods": ["..."],
  "references": ["..."],
  "clos": [{{"code":"CLO1","description":"mô tả tiếng Việt","description_en":"English translation","bloom_level":"remember|understand|apply|analyze|evaluate|create","plos":[{{"plo_code":"PLO1","level":"I|R|M"}}]}}],
  "assessments": [{{"name":"","type":"","weight_percent":0,"clo_codes":["CLO1"],"rubric":[{{"name":"tiêu chí","weight_percent":0,"levels":["Giỏi: ...","Khá: ...","Đạt: ...","Chưa đạt: ..."]}}]}}],
  "lessons": [{{"week":1,"topic":"","clo_codes":["CLO1"]}}]
}}
Chỉ dùng các mã PLO có trong dữ liệu được cung cấp. KHÔNG bịa PLO không tồn tại."""

# Các cơ cấu đánh giá định sẵn (tên hiển thị → mô tả cấu phần+trọng số).
ASSESSMENT_SCHEMES = {
    "10-30-60": "Dùng 3 cấu phần đánh giá: Chuyên cần 10%, Giữa kỳ 30%, Cuối kỳ 60%.",
    "10-40-50": "Dùng 3 cấu phần đánh giá: Chuyên cần 10%, Giữa kỳ 40%, Cuối kỳ 50%.",
    "20-30-50": "Dùng 3 cấu phần đánh giá: Đánh giá quá trình 20%, Giữa kỳ 30%, Cuối kỳ 50%.",
    "auto": "Tự đề xuất 3–4 cấu phần đánh giá với trọng số hợp lý cho học phần.",
}

BLOOM_STYLE_BILINGUAL = (
    "Viết SONG NGỮ ĐẦY ĐỦ: trường 'description' là mô tả CLO tiếng Việt (động từ Bloom "
    "tiếng Anh trong ngoặc ở đầu, ví dụ 'Phân tích (Analyze) các yếu tố...'); trường "
    "'description_en' là BẢN DỊCH TIẾNG ANH HOÀN CHỈNH của CLO đó."
)
BLOOM_STYLE_VI = (
    "Viết mô tả CLO ('description') bằng tiếng Việt với động từ Bloom rõ ràng; "
    "để trống 'description_en'."
)


def build_system_prompt(
    num_clos: str = "4–6",
    num_weeks: int = 15,
    assessment_scheme: str = "10-30-60",
    bilingual: bool = True,
) -> str:
    return OUTLINE_SYSTEM_PROMPT.format(
        num_clos=num_clos,
        num_weeks=num_weeks,
        assessment_rule=ASSESSMENT_SCHEMES.get(assessment_scheme, ASSESSMENT_SCHEMES["auto"]),
        bloom_style=BLOOM_STYLE_BILINGUAL if bilingual else BLOOM_STYLE_VI,
    )




def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end != -1 else t


# ---------------------------------------------------------------------------
# Phân tích (parse) đề cương ĐÃ CÓ từ văn bản upload thành cấu trúc chuẩn (SPEC 4.3)
# ---------------------------------------------------------------------------
PARSE_SYSTEM_PROMPT = """Bạn là chuyên gia thiết kế chương trình đào tạo theo OBE/AUN-QA. \
Bạn được cung cấp VĂN BẢN THÔ của một ĐỀ CƯƠNG HỌC PHẦN ĐÃ CÓ (trích từ file Word/PDF). \
Nhiệm vụ: BÓC TÁCH nội dung đề cương đó thành cấu trúc chuẩn — GIỮ NGUYÊN nội dung gốc, KHÔNG bịa thêm.

Quy tắc bóc tách:
- detected_course_code: mã học phần đọc được trong văn bản (nếu có), nếu không thì để rỗng.
- description: mô tả/giới thiệu học phần lấy từ văn bản.
- teaching_methods, references: liệt kê đúng những gì văn bản nêu (mỗi mục một phần tử).
- clos: mỗi CLO lấy đúng nội dung gốc; 'description' tiếng Việt; 'description_en' là bản dịch tiếng Anh \
(tự dịch nếu văn bản chưa có); 'bloom_level' suy ra từ động từ của CLO.
- Ánh xạ PLO: với mỗi CLO, CHỈ dùng các mã PLO có trong DANH SÁCH PLO được cung cấp. Nếu văn bản nêu rõ \
ánh xạ CLO–PLO thì theo đúng đó (kèm mức I/R/M nếu có); nếu KHÔNG rõ ràng thì để 'plos' rỗng \
(KHÔNG đoán bừa) — con người sẽ bổ sung sau.
- assessments: lấy đúng các cấu phần đánh giá + trọng số (%) trong văn bản; kèm rubric nếu có; \
'clo_codes' là các CLO mà cấu phần đó đánh giá (nếu văn bản nêu).
- lessons: lấy kế hoạch giảng dạy theo tuần/buổi nếu có (week, topic, clo_codes).

Chỉ trả về DUY NHẤT một JSON hợp lệ (không markdown, không văn bản thừa) theo schema:
{{
  "detected_course_code": "",
  "description": "",
  "teaching_methods": ["..."],
  "references": ["..."],
  "clos": [{{"code":"CLO1","description":"","description_en":"","bloom_level":"remember|understand|apply|analyze|evaluate|create","plos":[{{"plo_code":"PLO1","level":"I|R|M"}}]}}],
  "assessments": [{{"name":"","type":"","weight_percent":0,"clo_codes":["CLO1"],"rubric":[{{"name":"","weight_percent":0,"levels":["..."]}}]}}],
  "lessons": [{{"week":1,"topic":"","clo_codes":["CLO1"]}}]
}}
Chỉ dùng các mã PLO có trong dữ liệu được cung cấp. Nếu một thông tin không có trong văn bản, để trống/[]."""


def parse_outline_from_text(
    course: dict, plos: list[dict], pis: list[dict], text: str
) -> tuple[GeneratedOutline, str]:
    """Bóc tách đề cương đã có (văn bản thô) thành GeneratedOutline.

    Trả (outline, detected_course_code). Chỉ ánh xạ PLO trong danh sách được cấp;
    CLO không rõ PLO sẽ để trống cho con người bổ sung (human-in-the-loop).
    """
    if not (text or "").strip():
        raise ValueError("Văn bản đề cương rỗng — không bóc tách được.")
    plo_lines = "\n".join(
        f"- {p['code']} [{p.get('category','')}]: {p['description']}" for p in plos
    ) or "(chưa có PLO)"
    pi_lines = "\n".join(f"- {pi['code']} (thuộc {pi['plo_code']}): {pi['description']}" for pi in pis)
    parts = [
        f"HỌC PHẦN (theo hệ thống): {course.get('code','')} — {course.get('name','')}.",
        f"\nDANH SÁCH PLO CỦA CHƯƠNG TRÌNH (chỉ ánh xạ trong số này):\n{plo_lines}",
        f"\nCHỈ BÁO PI:\n{pi_lines}" if pi_lines else "",
        f"\n===== VĂN BẢN ĐỀ CƯƠNG ĐÃ CÓ (bóc tách nội dung này) =====\n\"\"\"\n{text[:40000]}\n\"\"\"",
    ]
    raw = llm_complete(PARSE_SYSTEM_PROMPT, "\n".join(p for p in parts if p), max_tokens=12000)
    data = json.loads(_strip_to_json(raw))
    detected = str(data.pop("detected_course_code", "") or "")
    return GeneratedOutline.model_validate(data), detected


IMPROVE_SYSTEM_PROMPT = """Bạn là chuyên gia thiết kế chương trình đào tạo theo chuẩn OBE \
(Outcome-Based Education) và kiểm định AUN-QA. Bạn được giao một ĐỀ CƯƠNG HỌC PHẦN hiện có \
KÈM KẾT QUẢ KIỂM TRA CHẤT LƯỢNG (AI) chỉ ra các lỗi/cảnh báo cần khắc phục.

Nhiệm vụ: NÂNG CẤP đề cương để khắc phục TỪNG điểm đã nêu trong kết quả kiểm tra, đồng thời \
GIỮ LẠI những phần đã tốt. Nguyên tắc:
- Xử lý DỨT ĐIỂM mọi 'errors' và cố gắng xử lý các 'warnings'; mỗi gợi ý sửa (suggestion) của \
từng CLO phải được phản ánh trong bản nâng cấp.
- Thống nhất phân loại thang đo: CLO thái độ (affective) dùng động từ/diễn đạt và hình thức đánh giá \
phù hợp (rubric quan sát, dự án, đánh giá quá trình) — KHÔNG ép vào thang Bloom nhận thức.
- Mỗi CLO chỉ tập trung MỘT động từ/mức chủ đạo, đo lường được, bắt đầu bằng động từ.
- MỖI CLO ánh xạ ít nhất một PLO (đúng mã PLO được cung cấp) với mức I/R/M hợp lý; cân nhắc ánh xạ \
chi tiết tới PI nếu kết quả kiểm tra yêu cầu phân hóa.
- MỖI CLO được phủ bởi ít nhất một cấu phần đánh giá VÀ xuất hiện trong kế hoạch giảng dạy; \
mọi hoạt động học (vd thuyết trình/dự án nhóm) tính điểm phải có cấu phần đánh giá với trọng số rõ ràng.
- Bổ sung cấu phần đánh giá quá trình khi CLO mức cao (Analyze trở lên) chỉ được đánh giá ở cuối kỳ.
- Tổng trọng số các cấu phần đánh giá BẰNG ĐÚNG 100.
- MỖI cấu phần đánh giá kèm RUBRIC: 2–4 tiêu chí (tổng trọng số tiêu chí = 100) và 3–4 mức chất lượng cụ thể.
- GIỮ NGUYÊN mã CLO sẵn có khi nội dung không đổi nhiều; chỉ thêm CLO mới khi thật cần.
- Viết SONG NGỮ: 'description' tiếng Việt (động từ Bloom/thái độ tiếng Anh trong ngoặc), \
'description_en' là bản dịch tiếng Anh đầy đủ.

Chỉ trả về DUY NHẤT một JSON hợp lệ (không markdown, không văn bản thừa) theo schema:
{{
  "description": "mô tả học phần",
  "teaching_methods": ["..."],
  "references": ["..."],
  "clos": [{{"code":"CLO1","description":"mô tả tiếng Việt","description_en":"English","bloom_level":"remember|understand|apply|analyze|evaluate|create","plos":[{{"plo_code":"PLO1","level":"I|R|M"}}]}}],
  "assessments": [{{"name":"","type":"","weight_percent":0,"clo_codes":["CLO1"],"rubric":[{{"name":"tiêu chí","weight_percent":0,"levels":["Giỏi: ...","Khá: ...","Đạt: ...","Chưa đạt: ..."]}}]}}],
  "lessons": [{{"week":1,"topic":"","clo_codes":["CLO1"]}}]
}}
Chỉ dùng các mã PLO có trong dữ liệu được cung cấp. KHÔNG bịa PLO không tồn tại."""


def _format_qa(qa: dict) -> str:
    """Định dạng kết quả kiểm tra chất lượng (AI) thành văn bản đưa vào prompt nâng cấp."""
    if not qa:
        return "(không có kết quả kiểm tra — hãy tự rà soát theo tiêu chí AUN-QA)"
    parts: list[str] = []
    if qa.get("summary"):
        parts.append(f"Nhận xét tổng quan: {qa['summary']}")
    if qa.get("score") is not None:
        parts.append(f"Điểm hiện tại: {qa['score']}/100")
    if qa.get("errors"):
        parts.append("LỖI cần sửa:\n" + "\n".join(f"- {e}" for e in qa["errors"]))
    if qa.get("warnings"):
        parts.append("CẢNH BÁO nên xử lý:\n" + "\n".join(f"- {w}" for w in qa["warnings"]))
    cr = qa.get("clo_reviews") or []
    if cr:
        lines = []
        for r in cr:
            issues = "; ".join(r.get("issues", []) or []) or "—"
            sug = r.get("suggestion", "") or ""
            lines.append(f"- {r.get('code','?')}: vấn đề: {issues}" + (f" | gợi ý: {sug}" if sug else ""))
        parts.append("Rà soát từng CLO:\n" + "\n".join(lines))
    return "\n\n".join(parts)


def improve_outline_ai(
    course: dict,
    plos: list[dict],
    pis: list[dict],
    course_plo: list[dict],
    current: dict,
    qa: dict,
) -> GeneratedOutline:
    """Nâng cấp đề cương hiện có dựa trên kết quả kiểm tra chất lượng (AI).

    current: {description, teaching_methods, references, clos:[{code,description,
        description_en,bloom_level,plos:[{plo_code,level}]}], assessments:[...], lessons:[...]}.
    qa: kết quả từ review_outline_ai (score/summary/errors/warnings/clo_reviews).
    Trả về GeneratedOutline đã validate — caller ghi ra một phiên bản đề cương mới (draft).
    """
    plo_lines = "\n".join(f"- {p['code']} [{p.get('category','')}]: {p['description']}" for p in plos)
    pi_lines = "\n".join(f"- {pi['code']} (thuộc {pi['plo_code']}): {pi['description']}" for pi in pis)
    cp_lines = "\n".join(f"- {cp['plo_code']}: mức {cp['level']}" for cp in course_plo) or "(chưa có)"

    def _clo_plo_str(c: dict) -> str:
        mapped = ", ".join(f"{m['plo_code']}({m.get('level', 'R')})" for m in c.get("plos", []))
        return mapped or "CHƯA ÁNH XẠ"

    cur_clo = "\n".join(
        f"- {c['code']} ({c.get('bloom_level','')}): {c['description']} [PLO: {_clo_plo_str(c)}]"
        for c in current.get("clos", [])
    ) or "(chưa có)"
    cur_assess = "\n".join(
        f"- {a['name']} ({a.get('type','')}, {a.get('weight_percent',0)}%) → CLO: "
        f"{', '.join(a.get('clo_codes', [])) or 'KHÔNG'}"
        for a in current.get("assessments", [])
    ) or "(chưa có)"
    cur_lesson = "\n".join(
        f"- Tuần {l.get('week','?')}: {l.get('topic','')} → CLO: {', '.join(l.get('clo_codes', [])) or 'KHÔNG'}"
        for l in current.get("lessons", [])
    ) or "(chưa có)"

    user_content = "\n".join(p for p in [
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')} "
        f"({course.get('credits','?')} tín chỉ, loại {course.get('type','')}).",
        f"CHƯƠNG TRÌNH ĐÀO TẠO: {course.get('program_name','')}.",
        f"\nDANH SÁCH PLO CỦA CHƯƠNG TRÌNH:\n{plo_lines}",
        f"\nCHỈ BÁO PI:\n{pi_lines}" if pi_lines else "",
        f"\nMỨC ĐÓNG GÓP HỌC PHẦN×PLO:\n{cp_lines}",
        f"\n===== ĐỀ CƯƠNG HIỆN TẠI =====\nMô tả: {current.get('description','')}",
        f"\nCLO HIỆN TẠI:\n{cur_clo}",
        f"\nĐÁNH GIÁ HIỆN TẠI:\n{cur_assess}",
        f"\nKẾ HOẠCH DẠY HIỆN TẠI:\n{cur_lesson}",
        f"\n===== KẾT QUẢ KIỂM TRA CHẤT LƯỢNG (AI) CẦN KHẮC PHỤC =====\n{_format_qa(qa)}",
        "\nHãy trả về đề cương ĐÃ NÂNG CẤP (toàn bộ, không chỉ phần sửa) khắc phục các điểm trên.",
    ] if p)

    raw = llm_complete(IMPROVE_SYSTEM_PROMPT, user_content, max_tokens=12000)
    data = json.loads(_strip_to_json(raw))
    return GeneratedOutline.model_validate(data)


def generate_outline_ai(
    course: dict,
    plos: list[dict],
    pis: list[dict],
    course_plo: list[dict],
    template_text: str = "",
    aunqa_text: str = "",
    num_clos: str = "4–6",
    num_weeks: int = 15,
    assessment_scheme: str = "10-30-60",
    bilingual: bool = True,
) -> GeneratedOutline:
    """Gọi Claude sinh đề cương; validate Pydantic. Cần ANTHROPIC_API_KEY.

    Tham số tinh chỉnh (theo quy định trường): số CLO, số tuần, cơ cấu đánh giá,
    CLO song ngữ Việt(Anh) hay chỉ tiếng Việt.
    """
    plo_lines = "\n".join(f"- {p['code']} [{p.get('category','')}]: {p['description']}" for p in plos)
    pi_lines = "\n".join(f"- {pi['code']} (thuộc {pi['plo_code']}): {pi['description']}" for pi in pis)
    cp_lines = "\n".join(f"- {cp['plo_code']}: mức {cp['level']}" for cp in course_plo) or "(chưa có)"

    parts = [
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')} "
        f"({course.get('credits','?')} tín chỉ, học kỳ {course.get('semester','?')}, loại {course.get('type','')}).",
        f"CHƯƠNG TRÌNH ĐÀO TẠO: {course.get('program_name','')}.",
        f"\nDANH SÁCH PLO CỦA CHƯƠNG TRÌNH:\n{plo_lines}",
        f"\nCHỈ BÁO PI:\n{pi_lines}" if pi_lines else "",
        f"\nMỨC ĐÓNG GÓP CỦA HỌC PHẦN NÀY VÀO PLO (ma trận Học phần×PLO):\n{cp_lines}",
    ]
    if template_text.strip():
        parts.append(f"\nMẪU ĐỀ CƯƠNG THAM KHẢO (bám cấu trúc/cách trình bày này):\n{template_text[:30000]}")
    if aunqa_text.strip():
        parts.append(f"\nTÀI LIỆU CHUẨN AUN-QA (đáp ứng các tiêu chí sau):\n{aunqa_text[:30000]}")
    parts.append(
        "\nHãy soạn đề cương cho học phần trên. Nếu ma trận Học phần×PLO có sẵn, "
        "ưu tiên ánh xạ CLO tới đúng các PLO đó với mức tương ứng."
    )
    user_content = "\n".join(p for p in parts if p)

    raw = llm_complete(
        build_system_prompt(num_clos, num_weeks, assessment_scheme, bilingual),
        user_content,
        max_tokens=12000,  # rubric + bản dịch EN làm output dài hơn
    )
    data = json.loads(_strip_to_json(raw))
    return GeneratedOutline.model_validate(data)
