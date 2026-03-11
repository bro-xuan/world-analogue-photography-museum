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
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo + Name */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-7 h-7 rounded-full bg-neutral-900 flex items-center justify-center shrink-0">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="5" stroke="white" strokeWidth="1.2" />
              <circle cx="7" cy="7" r="2" fill="white" />
            </svg>
          </div>
          <span className="font-display text-[15px] font-semibold text-neutral-900 tracking-tight hidden sm:block group-hover:text-neutral-600 transition-colors">
            WAPM
          </span>
        </Link>

        {/* Navigation */}
        <div className="flex items-center gap-1">
          <Link
            href="/"
            className={`px-3.5 py-1.5 text-[13px] rounded-full transition-colors ${
              pathname === "/"
                ? "bg-neutral-100 text-neutral-900 font-medium"
                : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50"
            }`}
          >
            Collection
          </Link>
          <Link
            href="/brands"
            className={`px-3.5 py-1.5 text-[13px] rounded-full transition-colors ${
              pathname.startsWith("/brands")
                ? "bg-neutral-100 text-neutral-900 font-medium"
                : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50"
            }`}
          >
            Brands
          </Link>

          <div className="w-px h-5 bg-neutral-200 mx-2" />

          {loading ? (
            <div className="w-8 h-8" />
          ) : user ? (
            <UserMenu />
          ) : (
            <button
              onClick={signIn}
              className="px-3.5 py-1.5 text-[13px] text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50 rounded-full transition-colors cursor-pointer"
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
