"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useMuseum } from "@/contexts/MuseumContext";
import UserMenu from "./auth/UserMenu";

export default function NavBar() {
  const { user, loading, signIn } = useAuth();
  const pathname = usePathname();
  const { triggerLeaveBrowse } = useMuseum();

  return (
    <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-lg border-b border-neutral-200/60">
      <div
        className="w-full px-8 flex items-center justify-between"
        style={{ height: "max(60px, 5.5vh)" }}
      >
        {/* Logo + Name */}
        <Link
          href="/"
          className="flex items-center gap-3 group"
          aria-label="Home"
          onClick={(e) => {
            if (pathname === "/") {
              e.preventDefault();
              triggerLeaveBrowse();
            }
          }}
        >
          <Image
            src="/logo.png"
            alt="WAPM"
            width={40}
            height={40}
            className="shrink-0"
            style={{ width: "max(32px, 3.5vh)", height: "auto" }}
          />
          <span
            className="font-bold text-neutral-900 tracking-tight hidden sm:block group-hover:text-neutral-600 transition-colors"
            style={{ fontSize: "max(14px, 1.4vh)", fontFamily: "var(--font-space-mono)" }}
          >
            analogcams.com
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
            onClick={(e) => {
              if (pathname === "/") {
                e.preventDefault();
                triggerLeaveBrowse();
              }
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
