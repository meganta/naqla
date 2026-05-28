import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/auth-provider";

export const metadata: Metadata = {
  title: "نقلة — منصة التعليم الذكي",
  description: "منصة نقلة للتعليم الذكي للمعلمين",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body className="min-h-screen bg-gray-50 font-arabic">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
