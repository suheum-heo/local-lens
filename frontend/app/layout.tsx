import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LocalLens — Local × Global restaurant discovery",
  description:
    "Discover restaurants in South Korea with Kakao local signals and Google global reviews.",
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
