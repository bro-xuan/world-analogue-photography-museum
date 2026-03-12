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
      <div
        className="w-full px-8 flex items-center justify-between"
        style={{ height: "max(60px, 5.5vh)" }}
      >
        {/* Logo + Name */}
        <Link href="/" className="flex items-center gap-3 group" aria-label="Home">
          <div
            className="rounded-full bg-neutral-900 flex items-center justify-center shrink-0"
            style={{ width: "max(32px, 3vh)", height: "max(32px, 3vh)" }}
          >
            <svg
              style={{ width: "max(16px, 1.5vh)", height: "max(16px, 1.5vh)" }}
              viewBox="0 0 14 14"
              fill="none"
            >
              <circle cx="7" cy="7" r="5" stroke="white" strokeWidth="1.2" />
              <circle cx="7" cy="7" r="2" fill="white" />
            </svg>
          </div>
          <span
            className="font-display font-semibold text-neutral-900 tracking-tight hidden sm:block group-hover:text-neutral-600 transition-colors"
            style={{ fontSize: "max(16px, 1.6vh)" }}
          >
            WAPM
          </span>
        </Link>

        {/* Navigation */}
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className={`rounded-full transition-colors ${
              pathname === "/"
                ? "bg-neutral-100 text-neutral-900 font-medium"
                : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50"
            }`}
            style={{
              padding: "max(8px, 0.7vh) max(18px, 1.6vh)",
              fontSize: "max(14px, 1.5vh)",
            }}
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
            style={{
              padding: "max(8px, 0.7vh) max(18px, 1.6vh)",
              fontSize: "max(14px, 1.5vh)",
            }}
          >
            Brands
          </Link>

          <div
            className="w-px bg-neutral-200 mx-3"
            style={{ height: "max(24px, 2.2vh)" }}
          />

          {loading ? (
            <div style={{ width: "max(36px, 3.5vh)", height: "max(36px, 3.5vh)" }} />
          ) : user ? (
            <UserMenu />
          ) : (
            <button
              onClick={signIn}
              className="text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50 rounded-full transition-colors cursor-pointer"
              style={{
                padding: "max(8px, 0.7vh) max(18px, 1.6vh)",
                fontSize: "max(14px, 1.5vh)",
              }}
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
