"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "", full_name: "", tenant_name: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const { access_token } = await api.auth.register(form);
      const user = await api.auth.me(access_token);
      login(access_token, user);
      router.push("/dashboard");
    } catch {
      setError("حدث خطأ أثناء إنشاء الحساب. تأكد من صحة البيانات.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-indigo-700 mb-2">نقلة</h1>
          <p className="text-gray-500">إنشاء حساب جديد</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {[
            { key: "full_name", label: "الاسم الكامل", type: "text", placeholder: "أحمد محمد" },
            { key: "email", label: "البريد الإلكتروني", type: "email", placeholder: "example@school.edu" },
            { key: "password", label: "كلمة المرور", type: "password", placeholder: "••••••••" },
            { key: "tenant_name", label: "اسم المدرسة أو المؤسسة", type: "text", placeholder: "مدرسة النور الثانوية" },
          ].map(({ key, label, type, placeholder }) => (
            <div key={key}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
              <input
                type={type}
                value={form[key as keyof typeof form]}
                onChange={e => setForm({ ...form, [key]: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-4 py-2 text-right focus:outline-none focus:ring-2 focus:ring-indigo-400"
                placeholder={placeholder} required
              />
            </div>
          ))}
          {error && <p className="text-red-500 text-sm text-center">{error}</p>}
          <button
            type="submit" disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg transition disabled:opacity-50"
          >
            {loading ? "جارٍ إنشاء الحساب..." : "إنشاء الحساب"}
          </button>
          <p className="text-center text-sm text-gray-500">
            لديك حساب؟{" "}
            <a href="/login" className="text-indigo-600 hover:underline">تسجيل الدخول</a>
          </p>
        </form>
      </div>
    </div>
  );
}
