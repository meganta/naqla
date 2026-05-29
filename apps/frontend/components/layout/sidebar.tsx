"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

const navItems = [
  { href: "/dashboard", label: "الرئيسية", icon: "🏠" },
  { href: "/knowledge", label: "مصادر المعرفة", icon: "📚" },
  { href: "/copilot", label: "المساعد الذكي", icon: "🤖" },
  { href: "/particles", label: "الجسيمات التعليمية", icon: "⚛️" },
  { href: "/curriculum", label: "خريطة المنهج", icon: "🗺️" },
  { href: "/marketplace", label: "السوق التعليمي", icon: "🏪" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <aside className="w-64 min-h-screen bg-white border-l border-gray-200 flex flex-col">
      <div className="p-6 border-b border-gray-100">
        <h1 className="text-2xl font-bold text-indigo-700">نقلة</h1>
        <p className="text-xs text-gray-400 mt-1">منصة التعليم الذكي</p>
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(item => (
          <Link
            key={item.href} href={item.href}
            className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition ${
              pathname === item.href
                ? "bg-indigo-50 text-indigo-700 font-medium"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
      <div className="p-4 border-t border-gray-100">
        <Link
          href="/settings"
          className={`flex items-center gap-3 px-4 py-2 rounded-lg text-sm transition mb-1 ${
            pathname === "/settings"
              ? "bg-indigo-50 text-indigo-700 font-medium"
              : "text-gray-600 hover:bg-gray-50"
          }`}
        >
          <span>⚙️</span>
          <span>{user?.full_name}</span>
        </Link>
        <button
          onClick={handleLogout}
          className="w-full text-right px-4 py-2 text-sm text-red-500 hover:bg-red-50 rounded-lg transition"
        >
          تسجيل الخروج
        </button>
      </div>
    </aside>
  );
}
