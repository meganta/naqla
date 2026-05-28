import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "نقلة — منصة التعليم الذكي",
  description: "منصة نقلة للتعليم الذكي للمعلمين",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ar" dir="rtl">
      <body className="min-h-screen bg-gray-50 font-arabic">
        {children}
      </body>
    </html>
  );
}
