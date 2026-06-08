import Link from "next/link";

// [icon, tiêu đề, mô tả, link]
const MODULES: [string, string, string, string?][] = [
  ["📥", "Trích xuất đề án (AI)", "Upload PDF/DOCX → AI trích PLO/PI/học phần → con người rà soát.", "/extract"],
  ["🎯", "CTĐT & Chuẩn đầu ra", "Program, PLO, PI, học phần, ma trận Học phần×PLO, kiểm tra độ phủ.", "/programs"],
  ["📋", "Đề cương học phần", "CLO, ma trận CLO×PLO, đánh giá + rubric, alignment, versioning.", "/programs"],
  ["📚", "Giáo trình & Bài giảng", "Soạn theo chương gắn CLO; AI tạo & nâng cấp; xuất DOCX/PDF/PPTX.", "/programs"],
  ["🏦", "Ngân hàng câu hỏi", "Sinh câu hỏi gắn CLO/Bloom/độ khó; thẩm định; ma trận đề thi.", "/programs"],
  ["📝", "Tạo đề thi", "Sinh đề từ ma trận, nhiều mã đề, bảng đặc tả + đáp án; vòng đời duyệt.", "/programs"],
  ["🛡️", "Lưu trữ & Kiểm định", "Báo cáo phủ chuẩn PLO→PI→CLO→đánh giá; audit log; gói minh chứng.", "/qa"],
];

export default function Home() {
  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-indigo-600 via-indigo-600 to-violet-600 p-8 text-white shadow-soft sm:p-12">
        <span className="badge bg-white/15 text-white ring-1 ring-white/20">Có AI đồng hành toàn chuỗi</span>
        <h1 className="mt-3 max-w-3xl text-3xl font-bold tracking-tight !text-white sm:text-4xl">
          Nền tảng Quản lý Đào tạo theo Chuẩn đầu ra (OBE) &amp; Kiểm định AUN-QA
        </h1>
        <p className="mt-3 max-w-2xl text-indigo-100">
          Số hóa toàn bộ chuỗi học thuật: Đề án → CTĐT/PLO → Đề cương/CLO → Giáo trình →
          Ngân hàng câu hỏi → Đề thi → Minh chứng kiểm định. AI vừa tạo nội dung, vừa thẩm định
          &amp; nâng cấp chất lượng — truy vết chuẩn đầu ra xuyên suốt.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/extract" className="btn bg-white text-indigo-700 hover:bg-indigo-50">
            Trích xuất đề án (AI) →
          </Link>
          <Link href="/programs" className="btn border border-white/40 text-white hover:bg-white/10">
            Danh sách CTĐT
          </Link>
        </div>
      </section>

      {/* Module grid */}
      <section>
        <h2 className="mb-4">Phân hệ chính</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {MODULES.map(([icon, title, desc, href]) => {
            const card = (
              <div className="group h-full rounded-xl border border-slate-200 bg-white p-5 shadow-card transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-soft">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 text-lg">
                    {icon}
                  </span>
                  <h3 className="text-slate-900 group-hover:text-indigo-700">{title}</h3>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-slate-600">{desc}</p>
              </div>
            );
            return href ? (
              <Link key={title} href={href}>{card}</Link>
            ) : (
              <div key={title}>{card}</div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
