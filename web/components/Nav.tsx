"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Now showing" },
  { href: "/profile", label: "Liked" },
  { href: "/debug", label: "Ranking" },
  { href: "/system", label: "Booth" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <header className="topbar">
      <Link href="/" className="brand" aria-label="Watch Next home">
        <span className="brand-mark" aria-hidden="true" />
        Watch Next
      </Link>
      <nav className="nav-links">
        {LINKS.map((link) => (
          <Link key={link.href} href={link.href} className={path === link.href ? "active" : undefined}>
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
