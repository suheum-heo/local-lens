import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LocalLens — 두 시선이 만나는 진짜 맛집",
  description:
    "LocalLens — Kakao(로컬)와 Google(글로벌) 시선으로 함께 비교해 더 믿을 수 있는 맛집을 고릅니다.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
