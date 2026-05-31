"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
}

interface Program {
  id: number;
  name: string;
  code: string;
}

interface Course {
  id: number;
  name: string;
  code?: string;
}

interface Assignment {
  id: number;
  user_id: number;
  program_id: number | null;
  course_id: number | null;
  role: string;
}

const ROLE_LABELS: Record<string, string> = {
  admin: "Quản trị",
  program_manager: "Quản lý CTĐT",
  lecturer: "Giảng viên",
  qa: "ĐBCL",
  guest: "Khách",
};

const ROLES = ["admin", "program_manager", "lecturer", "qa", "guest"];

export default function AdminPage() {
  const router = useRouter();

  const [users, setUsers] = useState<User[]>([]);
  const [usersErr, setUsersErr] = useState("");
  const [userForm, setUserForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "lecturer",
  });
  const [userFormErr, setUserFormErr] = useState("");

  const [programs, setPrograms] = useState<Program[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);

  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [assignmentsErr, setAssignmentsErr] = useState("");
  const [assignForm, setAssignForm] = useState({
    user_id: "",
    program_id: "",
    course_id: "",
    role: "lecturer",
  });
  const [assignFormErr, setAssignFormErr] = useState("");

  function friendlyErr(e: any): string {
    const msg = String(e?.message || e || "");
    if (msg.includes("403") || /forbidden|permission|quyền/i.test(msg)) {
      return "Bạn không có quyền thực hiện thao tác này";
    }
    return msg || "Có lỗi xảy ra";
  }

  async function loadUsers() {
    setUsersErr("");
    try {
      setUsers(await api("/api/auth/users"));
    } catch (e: any) {
      setUsersErr(friendlyErr(e));
    }
  }

  async function loadPrograms() {
    try {
      setPrograms(await api("/api/programs"));
    } catch {
      // bỏ qua, dropdown sẽ rỗng
    }
  }

  async function loadAssignments() {
    setAssignmentsErr("");
    try {
      setAssignments(await api("/api/assignments"));
    } catch (e: any) {
      setAssignmentsErr(friendlyErr(e));
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    loadUsers();
    loadPrograms();
    loadAssignments();
  }, []);

  async function loadCourses(pid: string) {
    if (!pid) {
      setCourses([]);
      return;
    }
    try {
      setCourses(await api(`/api/programs/${pid}/courses`));
    } catch {
      setCourses([]);
    }
  }

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setUserFormErr("");
    try {
      await api("/api/auth/users", {
        method: "POST",
        body: JSON.stringify(userForm),
      });
      setUserForm({ name: "", email: "", password: "", role: "lecturer" });
      loadUsers();
    } catch (e: any) {
      setUserFormErr(friendlyErr(e));
    }
  }

  async function createAssignment(e: React.FormEvent) {
    e.preventDefault();
    setAssignFormErr("");
    if (!assignForm.user_id) {
      setAssignFormErr("Vui lòng chọn người dùng");
      return;
    }
    try {
      const body = {
        user_id: Number(assignForm.user_id),
        program_id: assignForm.program_id
          ? Number(assignForm.program_id)
          : null,
        course_id: assignForm.course_id ? Number(assignForm.course_id) : null,
        role: assignForm.role,
      };
      await api("/api/assignments", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setAssignForm({
        user_id: "",
        program_id: "",
        course_id: "",
        role: "lecturer",
      });
      setCourses([]);
      loadAssignments();
    } catch (e: any) {
      setAssignFormErr(friendlyErr(e));
    }
  }

  async function deleteAssignment(aid: number) {
    setAssignmentsErr("");
    try {
      await api(`/api/assignments/${aid}`, { method: "DELETE" });
      loadAssignments();
    } catch (e: any) {
      setAssignmentsErr(friendlyErr(e));
    }
  }

  function userName(uid: number): string {
    const u = users.find((x) => x.id === uid);
    return u ? `${u.name} (${u.email})` : String(uid);
  }

  function programName(pid: number | null): string {
    if (pid == null) return "—";
    const p = programs.find((x) => x.id === pid);
    return p ? `${p.name} (${p.code})` : String(pid);
  }

  return (
    <div>
      <h1 className="text-2xl font-bold">Quản trị người dùng &amp; phân công</h1>

      {/* Section: Người dùng */}
      <div className="mt-4 rounded border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">Người dùng</h2>
        {usersErr && <p className="mt-2 text-sm text-red-600">{usersErr}</p>}
        {!usersErr && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 text-left">
                  <th className="border p-2">Tên</th>
                  <th className="border p-2">Email</th>
                  <th className="border p-2">Vai trò</th>
                  <th className="border p-2">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="border p-2">{u.name}</td>
                    <td className="border p-2">{u.email}</td>
                    <td className="border p-2">
                      {ROLE_LABELS[u.role] || u.role}
                    </td>
                    <td className="border p-2">
                      {u.is_active ? (
                        <span className="text-green-700">Hoạt động</span>
                      ) : (
                        <span className="text-red-700">Khóa</span>
                      )}
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td className="border p-2 text-slate-500" colSpan={4}>
                      Chưa có người dùng.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <form onSubmit={createUser} className="mt-4 flex flex-wrap gap-2">
          <input
            className="rounded border p-2"
            placeholder="Tên"
            value={userForm.name}
            onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
          />
          <input
            className="rounded border p-2"
            placeholder="Email"
            type="email"
            value={userForm.email}
            onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
          />
          <input
            className="rounded border p-2"
            placeholder="Mật khẩu"
            type="password"
            value={userForm.password}
            onChange={(e) =>
              setUserForm({ ...userForm, password: e.target.value })
            }
          />
          <select
            className="rounded border p-2"
            value={userForm.role}
            onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
          <button className="rounded bg-indigo-600 px-4 py-2 text-white">
            Tạo người dùng
          </button>
        </form>
        {userFormErr && (
          <p className="mt-2 text-sm text-red-600">{userFormErr}</p>
        )}
      </div>

      {/* Section: Phân công phụ trách */}
      <div className="mt-4 rounded border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">Phân công phụ trách</h2>

        <form onSubmit={createAssignment} className="mt-3 flex flex-wrap gap-2">
          <select
            className="rounded border p-2"
            value={assignForm.user_id}
            onChange={(e) =>
              setAssignForm({ ...assignForm, user_id: e.target.value })
            }
          >
            <option value="">-- Chọn người dùng --</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.email})
              </option>
            ))}
          </select>
          <select
            className="rounded border p-2"
            value={assignForm.program_id}
            onChange={(e) => {
              setAssignForm({
                ...assignForm,
                program_id: e.target.value,
                course_id: "",
              });
              loadCourses(e.target.value);
            }}
          >
            <option value="">-- Chọn CTĐT --</option>
            {programs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.code})
              </option>
            ))}
          </select>
          <select
            className="rounded border p-2"
            value={assignForm.course_id}
            onChange={(e) =>
              setAssignForm({ ...assignForm, course_id: e.target.value })
            }
            disabled={!assignForm.program_id}
          >
            <option value="">-- Học phần (tùy chọn) --</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.code ? ` (${c.code})` : ""}
              </option>
            ))}
          </select>
          <select
            className="rounded border p-2"
            value={assignForm.role}
            onChange={(e) =>
              setAssignForm({ ...assignForm, role: e.target.value })
            }
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
          <button className="rounded bg-indigo-600 px-4 py-2 text-white">
            Phân công
          </button>
        </form>
        {assignFormErr && (
          <p className="mt-2 text-sm text-red-600">{assignFormErr}</p>
        )}

        {assignmentsErr && (
          <p className="mt-3 text-sm text-red-600">{assignmentsErr}</p>
        )}
        {!assignmentsErr && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 text-left">
                  <th className="border p-2">Người dùng</th>
                  <th className="border p-2">CTĐT</th>
                  <th className="border p-2">Học phần</th>
                  <th className="border p-2">Vai trò</th>
                  <th className="border p-2"></th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((a) => (
                  <tr key={a.id}>
                    <td className="border p-2">{userName(a.user_id)}</td>
                    <td className="border p-2">{programName(a.program_id)}</td>
                    <td className="border p-2">
                      {a.course_id != null ? a.course_id : "—"}
                    </td>
                    <td className="border p-2">
                      {ROLE_LABELS[a.role] || a.role}
                    </td>
                    <td className="border p-2">
                      <button
                        className="rounded bg-red-600 px-3 py-1 text-white"
                        onClick={() => deleteAssignment(a.id)}
                      >
                        Xóa
                      </button>
                    </td>
                  </tr>
                ))}
                {assignments.length === 0 && (
                  <tr>
                    <td className="border p-2 text-slate-500" colSpan={5}>
                      Chưa có phân công.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
