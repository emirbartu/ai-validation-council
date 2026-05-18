import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/navigation";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AI Validation Council",
  description: "Multi-agent adversarial analysis for startup ideas",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} dark h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Navigation />
        <main className="flex-1">{children}</main>
        <footer className="border-t border-border/40 py-4">
          <div className="mx-auto max-w-6xl px-4 text-center text-xs text-muted-foreground">
            AI Validation Council - Divergence is the signal
          </div>
        </footer>
      </body>
    </html>
  );
}
