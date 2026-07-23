import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SFRFR — кабинет сотрудников",
  description: "Рабочее место оператора, эксперта и администратора",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
