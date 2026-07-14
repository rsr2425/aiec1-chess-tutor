"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { APP_NAME } from "@/lib/branding";

const TABS = [
  { href: "/coach", label: "Coach" },
  { href: "/guide", label: "Guide" },
];

/** Split wordmark: "Blunder" reads negative (red), the rest positive (green). */
function Wordmark() {
  const m = APP_NAME.match(/^(Blunder)(.+)$/i);
  if (!m) return <span className="text-amber-400">{APP_NAME}</span>;
  return (
    <>
      <span className="text-red-400">{m[1]}</span>
      <span className="text-green-400">{m[2]}</span>
    </>
  );
}

export default function Header({ username }: { username?: string }) {
  const pathname = usePathname();

  return (
    <header className="flex items-center justify-between border-b border-stone-800 bg-stone-900 px-6 py-3">
      <div className="flex items-center gap-6">
        <Link href="/coach" className="font-bold text-lg">
          <Wordmark />
        </Link>
        <nav className="flex gap-1">
          {TABS.map((tab) => (
            <Link
              key={tab.href}
              href={tab.href}
              className={`rounded-md px-3 py-1 text-sm transition-colors ${
                pathname === tab.href
                  ? "bg-stone-800 text-amber-300"
                  : "text-stone-400 hover:text-stone-200"
              }`}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
      </div>
      {username && <span className="text-sm text-stone-400">Playing as {username}</span>}
    </header>
  );
}
