"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearToken, getUser } from "@/lib/api";

const ROLE_LABEL: Record<string, string> = {
  super_admin: "Super Admin",
  admin: "Quản trị trường",
  program_manager: "Trưởng khoa",
  lecturer: "Giảng viên",
  qa: "ĐBCL",
  guest: "Khách",
};

export default function Nav() {
  const [user, setUser] = useState<any>(null);
  const router = useRouter();
  const pathname = usePathname() || "/";
  useEffect(() => setUser(getUser()), [pathname]);

  const link = (href: string, label: string) => {
    const active = pathname === href || (href !== "/" && pathname.startsWith(href));
    return (
      <Link
        href={href}
        className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
          active ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        }`}
      >
        {label}
      </Link>
    );
  };

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-500 text-sm font-bold text-white shadow-sm">
            OB
          </span>
          <span className="text-base font-bold tracking-tight text-slate-900">
            EduOBE <span className="font-normal text-slate-400">· AUN-QA</span>
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {link("/extract", "Trích xuất AI")}
          {link("/programs", "CTĐT")}
          {link("/qa", "Kiểm định")}
          {user && user.role === "super_admin" && link("/admin/tenants", "🏛 Nền tảng")}
          {user && (user.role === "admin" || user.role === "program_manager") && link("/admin", "Quản trị")}

          <span className="mx-1 h-5 w-px bg-slate-200" />

          {user ? (
            <div className="flex items-center gap-2">
              <span className="hidden items-center gap-1.5 sm:flex">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                  {(user.name || "?").trim().charAt(0).toUpperCase()}
                </span>
                <span className="text-xs leading-tight">
                  <span className="block font-medium text-slate-700">{user.name}</span>
                  <span className="block text-slate-400">{ROLE_LABEL[user.role] || user.role}</span>
                </span>
              </span>
              <button
                onClick={() => { clearToken(); router.push("/login"); }}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
              >
                Đăng xuất
              </button>
            </div>
          ) : (
            <Link href="/login" className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">
              Đăng nhập
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
