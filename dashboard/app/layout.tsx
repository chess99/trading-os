import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const origin = `${protocol}://${host}`;
  const description = "A股全市场五年基准情景年化回报、合理价值位置与正式研报阅读工作台。";
  return {
    metadataBase: new URL(origin),
    title: {
      default: "Trading OS · 全市场研究系统",
      template: "%s · Trading OS",
    },
    description,
    openGraph: {
      title: "Trading OS · 全市场研究决策台",
      description,
      type: "website",
      images: [
        {
          url: `${origin}/og.png`,
          width: 1729,
          height: 910,
          alt: "Trading OS 赔率地图",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Trading OS · 全市场研究决策台",
      description,
      images: [`${origin}/og.png`],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
