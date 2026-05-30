import Link from "next/link";

const MODULES = [
  ["Trích xuất đề án (AI)", "Upload PDF/DOCX → Claude trích xuất PLO/PI/học phần → con người rà soát."],
  ["CTĐT & Chuẩn đầu ra", "Quản lý Program, PLO, PI, học phần, ma trận Học phần×PLO, kiểm tra độ phủ."],
  ["Đề cương học phần", "CLO, ma trận CLO×PLO, đánh giá + rubric, kế hoạch dạy; kiểm tra alignment; versioning."],
  ["Giáo trình", "Soạn theo chương gắn CLO; phiên bản; xuất file."],
  ["Ngân hàng câu hỏi", "CRUD câu hỏi gắn CLO/Bloom/độ khó; thống kê lỗ hổng; ma trận đề thi."],
  ["Tạo đề thi", "Sinh đề từ ma trận, nhiều mã đề, bảng đặc tả + đáp án; vòng đời duyệt."],
  ["Lưu trữ & Kiểm định", "Báo cáo phủ chuẩn PLO→PI→CLO→đánh giá; audit log; gói minh chứng AUN-QA."],
];

export default function Home() {
  return (
    <div>
      <h1 className="text-3xl font-bold">Hệ thống OBE / AUN-QA</h1>
      <p className="mt-2 text-slate-600">
        Quản lý chuỗi sản phẩm học thuật theo chuẩn OBE: Đề án → CTĐT/PLO → Đề cương/CLO →
        Giáo trình → Ngân hàng câu hỏi → Đề thi → Minh chứng kiểm định.
      </p>
      <div className="mt-6">
        <Link href="/programs" className="rounded bg-indigo-600 px-4 py-2 text-white">
          Vào danh sách CTĐT →
        </Link>
      </div>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {MODULES.map(([title, desc]) => (
          <div key={title} className="rounded-lg border bg-white p-4 shadow-sm">
            <h3 className="font-semibold text-indigo-700">{title}</h3>
            <p className="mt-1 text-sm text-slate-600">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
