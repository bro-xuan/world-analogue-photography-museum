"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import UserMenu from "./auth/UserMenu";

export default function NavBar() {
  const { user, loading, signIn } = useAuth();
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-lg border-b border-neutral-200/60">
      <div className="w-full px-8 flex items-center justify-between" style={{ height: "max(56px, 4.5vh)" }}>
        {/* Logo + Name */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="rounded-full bg-neutral-900 flex items-center justify-center shrink-0" style={{ width: "max(28px, 2.5vh)", height: "max(28px, 2.5vh)" }}>
            <svg style={{ width: "max(14px, 1.3vh)", height: "max(14px, 1.3vh)" }} viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="5" stroke="white" strokeWidth="1.2" />
              <circle cx="7" cy="7" r="2" fill="white" />
            </svg>
          </div>
          <span className="font-display font-semibold text-neutral-900 tracking-tight hidden sm:block group-hover:text-neutral-600 transition-colors" style={{ fontSize: "max(15px, 1.4vh)" }}>
            WAPM
          </span>
        </Link>

        {/* Navigation */}
        <div className="flex items-center gap-1.5">
          <Link
            href="/"
            className={`rounded-full transition-colors ${
              pathname === "/"
                ? "bg-neutral-100 text-neutral-900 font-medium"
                : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50"
            }`}
            style={{ padding: "max(6px, 0.5vh) max(14px, 1.2vh)", fontSize: "max(13px, 1.3vh)" }}
          >
            Collection
          </Link>
          <Link
            href="/brands"
            className={`rounded-full transition-colors ${
              pathname.startsWith("/brands")
                ? "bg-neutral-100 text-neutral-900 font-medium"
                : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50"
            }`}
            style={{ padding: "max(6px, 0.5vh) max(14px, 1.2vh)", fontSize: "max(13px, 1.3vh)" }}
          >
            Brands
          </Link>

          <div className="w-px bg-neutral-200 mx-2.5" style={{ height: "max(20px, 2vh)" }} />

          {loading ? (
            <div style={{ width: "max(32px, 2.5vh)", height: "max(32px, 2.5vh)" }} />
          ) : user ? (
            <UserMenu />
          ) : (
            <button
              onClick={signIn}
              className="text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50 rounded-full transition-colors cursor-pointer"
              style={{ padding: "max(6px, 0.5vh) max(14px, 1.2vh)", fontSize: "max(13px, 1.3vh)" }}
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
