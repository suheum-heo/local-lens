import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LocalLens — 두 시선이 만나는 진짜 맛집",
  description:
    "Kakao와 Google 데이터를 함께 비교해 더 신뢰할 수 있는 맛집을 찾습니다.",
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
