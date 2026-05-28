"use client";
import { useAuth } from "@/lib/auth";

const cards = [
  { label: "مصادر المعرفة", icon: "📚", href: "/knowledge" },
  { label: "الجسيمات التعليمية", icon: "⚛️", href: "/particles" },
  { label: "المساعد الذكي", icon: "🤖", href: "/copilot" },
];

export default function DashboardPage() {
  const { user } = useAuth();
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800">
          أهلاً {user?.full_name}
        </h2>
        <p className="text-gray-500 mt-1">مرحباً بك في منصة نقلة</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {cards.map((card) => (
          <a key={card.label} href={card.href}
            className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-md transition">
            <div className="text-3xl mb-3">{card.icon}</div>
            <p className="text-gray-500 text-sm">{card.label}</p>
          </a>
        ))}
      </div>
    </div>
  );
}
