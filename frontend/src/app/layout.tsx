import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "UnityTrack | Railway Operations Decision Platform",
  description: "AI-powered decision-support platform for Indian Railways maintenance planning",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased font-sans">
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-100">
        <Providers>
          <Navbar />
          <div className="flex-1">{children}</div>
        </Providers>
      </body>
    </html>
  );
}
