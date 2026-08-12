import type { Metadata } from "next";
// Self-host Manrope (без next/font/google) — CI/VPS не зависят от fonts.gstatic.com
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Проверка стажа — кабинет клиента",
  description: "Защищённый кабинет сопровождения пенсионного дела",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body style={{ fontFamily: '"Manrope", "Segoe UI", sans-serif' }}>{children}</body>
    </html>
  );
}
