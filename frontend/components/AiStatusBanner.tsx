"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, getToken, getUser } from "@/lib/api";

/**
 * Banner cảnh báo toàn cục: khi đăng nhập mà hệ thống chưa có API key AI active,
 * nhắc admin cấu hình. Admin thấy link tới trang cấu hình; người khác thấy nhắc liên hệ admin.
 */
export default function AiStatusBanner() {
  const [status, setStatus] = useState<any>(null);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    if (!getToken()) return;
    setUser(getUser());
    api("/api/ai-status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status || status.configured) return null;

  const isAdmin = user?.role === "admin";
  return (
    <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
        <span>
          ⚠ <b>Chưa cấu hình API AI.</b> Các tính năng AI (trích xuất đề án, soạn đề cương,
          giáo trình, sinh câu hỏi) sẽ không hoạt động cho đến khi có API key được kích hoạt.
        </span>
        {isAdmin ? (
          <Link
            href="/admin/ai"
            className="whitespace-nowrap rounded bg-amber-600 px-3 py-1 text-white hover:bg-amber-700"
          >
            Cấu hình API ngay →
          </Link>
        ) : (
          <span className="whitespace-nowrap text-amber-700">Vui lòng liên hệ quản trị viên.</span>
        )}
      </div>
    </div>
  );
}
