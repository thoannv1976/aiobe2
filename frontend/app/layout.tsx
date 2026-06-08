import "./globals.css";
import type { Metadata } from "next";
import Nav from "@/components/Nav";
import AiStatusBanner from "@/components/AiStatusBanner";

export const metadata: Metadata = {
  title: "EduOBE · OBE / AUN-QA",
  description: "Quản lý Đề cương – Giáo trình – Ngân hàng câu hỏi – Đề thi theo chuẩn OBE/AUN-QA",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="flex min-h-screen flex-col font-sans">
        <Nav />
        <AiStatusBanner />
        <main className="mx-auto w-full max-w-6xl flex-1 p-6">{children}</main>
        <footer className="border-t border-slate-200 bg-white/60">
          <div className="mx-auto max-w-6xl px-6 py-4 text-center text-xs text-slate-400">
            EduOBE — Nền tảng Quản lý Đào tạo theo Chuẩn đầu ra (OBE) &amp; Kiểm định AUN-QA
          </div>
        </footer>
      </body>
    </html>
  );
}
