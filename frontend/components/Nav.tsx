"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearToken, getUser } from "@/lib/api";

export default function Nav() {
  const [user, setUser] = useState<any>(null);
  const router = useRouter();
  useEffect(() => setUser(getUser()), []);

  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between p-4">
        <Link href="/" className="font-bold text-indigo-700">
          OBE / AUN-QA
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/extract" className="hover:text-indigo-700">Trích xuất AI</Link>
          <Link href="/programs" className="hover:text-indigo-700">CTĐT</Link>
          <Link href="/qa" className="hover:text-indigo-700">Kiểm định</Link>
          {user && (user.role === "admin" || user.role === "program_manager") && (
            <Link href="/admin" className="hover:text-indigo-700">Quản trị</Link>
          )}
          {user ? (
            <>
              <span className="text-slate-500">
                {user.name} ({user.role})
              </span>
              <button
                onClick={() => {
                  clearToken();
                  router.push("/login");
                }}
                className="rounded bg-slate-100 px-3 py-1 hover:bg-slate-200"
              >
                Đăng xuất
              </button>
            </>
          ) : (
            <Link href="/login" className="rounded bg-indigo-600 px-3 py-1 text-white">
              Đăng nhập
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
