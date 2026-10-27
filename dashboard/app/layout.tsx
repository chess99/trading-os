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
  const description = "覆盖A股、港股与美股的价值投资研究工作台，连接公司、行业、宏观与市场估值。";
  return {
    metadataBase: new URL(origin),
    title: {
      default: "Trading OS · 价值投资研究",
      template: "%s · Trading OS",
    },
    description,
    openGraph: {
      title: "Trading OS · 价值投资研究",
      description,
      type: "website",
      images: [
        {
          url: `${origin}/og.png`,
          width: 1729,
          height: 910,
          alt: "Trading OS 价值投资研究",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Trading OS · 价值投资研究",
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
