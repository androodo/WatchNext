import type { ReactNode } from "react";
import "./globals.css";
import Link from "next/link";

export const metadata = { title: "PulseRank", description: "Real-time personalized recommendations" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <strong>PulseRank</strong>
          <Link href="/">Feed</Link>
          <Link href="/profile">Profile</Link>
          <Link href="/debug">Debug</Link>
          <Link href="/system">System</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
