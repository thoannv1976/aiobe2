import "./globals.css";
import type { Metadata } from "next";
import Nav from "@/components/Nav";
import AiStatusBanner from "@/components/AiStatusBanner";

export const metadata: Metadata = {
  title: "OBE / AUN-QA",
  description: "Quản lý Đề cương – Giáo trình – Ngân hàng câu hỏi – Đề thi (OBE/AUN-QA)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <Nav />
        <AiStatusBanner />
        <main className="mx-auto max-w-6xl p-6">{children}</main>
      </body>
    </html>
  );
}
