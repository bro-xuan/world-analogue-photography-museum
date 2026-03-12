"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useUserData } from "@/contexts/UserDataContext";
import { CameraEntry, fetchLandingData } from "@/lib/cameras";
import CameraTile from "@/components/CameraTile";

type Tab = "favorites" | "owned" | "wishlist";

const TABS: { key: Tab; label: string; icon: React.ReactNode; emptyText: string }[] = [
  {
    key: "favorites",
    label: "Favorites",
    icon: (
      <svg style={{ width: "max(16px, 1.5vh)", height: "max(16px, 1.5vh)" }} viewBox="0 0 24 24" fill="currentColor" stroke="none">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    ),
    emptyText: "Browse the collection and favorite what you want to remember.",
  },
  {
    key: "owned",
    label: "Owned",
    icon: (
      <svg style={{ width: "max(16px, 1.5vh)", height: "max(16px, 1.5vh)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    ),
    emptyText: "Mark cameras you own to build your collection.",
  },
  {
    key: "wishlist",
    label: "Wishlist",
    icon: (
      <svg style={{ width: "max(16px, 1.5vh)", height: "max(16px, 1.5vh)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
    emptyText: "Add cameras to your wishlist to track what you want next.",
  },
];

export default function ProfilePage() {
  const { user, loading: authLoading, signIn, signOut } = useAuth();
  const { owned, favorites, wishlist } = useUserData();
  const [cameras, setCameras] = useState<CameraEntry[]>([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>("favorites");

  useEffect(() => {
    fetchLandingData()
      .then((data) => {
        setCameras(data.cameras);
        setDataLoading(false);
      })
      .catch(() => setDataLoading(false));
  }, []);

  const counts = {
    favorites: favorites.size,
    owned: owned.size,
    wishlist: wishlist.size,
  };

  const setForTab: Record<Tab, Set<string>> = { favorites, owned, wishlist };
  const activeCameras = cameras.filter((c) => setForTab[activeTab].has(c.id));
  const activeTabDef = TABS.find((t) => t.key === activeTab)!;

  const loading = authLoading || dataLoading;

  return (
    <div className="min-h-screen bg-white">
      <main
        className="mx-auto"
        style={{ maxWidth: "max(900px, 75vw)", padding: "max(40px, 4vh) max(24px, 2vw) max(64px, 6vh)" }}
      >
        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-900 rounded-full animate-spin" />
          </div>
        ) : !user ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <h1
              className="font-display font-bold text-neutral-900"
              style={{ fontSize: "max(24px, 2.4vh)", marginBottom: "max(8px, 0.8vh)" }}
            >
              My Collection
            </h1>
            <p
              className="text-neutral-400"
              style={{ fontSize: "max(14px, 1.4vh)", marginBottom: "max(24px, 2.2vh)" }}
            >
              Sign in to start tracking cameras you own and your favorites.
            </p>
            <button
              onClick={signIn}
              className="flex items-center gap-2 font-medium text-neutral-700 border border-neutral-200 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer"
              style={{
                padding: "max(10px, 1vh) max(20px, 2vh)",
                fontSize: "max(14px, 1.4vh)",
              }}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
              Sign in with Google
            </button>
          </div>
        ) : (
          <>
            {/* Profile header */}
            <div
              className="flex items-start justify-between"
              style={{ marginBottom: "max(32px, 3vh)" }}
            >
              <div
                className="flex items-center"
                style={{ gap: "max(20px, 2vh)" }}
              >
                {user.photoURL ? (
                  <img
                    src={user.photoURL}
                    alt=""
                    className="rounded-full"
                    style={{ width: "max(80px, 8vh)", height: "max(80px, 8vh)" }}
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div
                    className="rounded-full bg-neutral-200 flex items-center justify-center font-medium text-neutral-600"
                    style={{
                      width: "max(80px, 8vh)",
                      height: "max(80px, 8vh)",
                      fontSize: "max(24px, 2.4vh)",
                    }}
                  >
                    {(user.displayName || user.email || "?")[0].toUpperCase()}
                  </div>
                )}
                <div>
                  <h1
                    className="font-display font-bold text-neutral-900"
                    style={{ fontSize: "max(20px, 2vh)" }}
                  >
                    {user.displayName}
                  </h1>
                  {/* Stats row */}
                  <div
                    className="flex items-center mt-2"
                    style={{ gap: "max(16px, 1.5vh)" }}
                  >
                    {TABS.map((tab, i) => (
                      <span key={tab.key} className="flex items-center gap-1">
                        {i > 0 && (
                          <span
                            className="text-neutral-200"
                            style={{ marginRight: "max(12px, 1vh)" }}
                          >
                            |
                          </span>
                        )}
                        <span
                          className="font-semibold text-neutral-900"
                          style={{ fontSize: "max(16px, 1.6vh)" }}
                        >
                          {counts[tab.key]}
                        </span>
                        <span
                          className="text-neutral-400"
                          style={{ fontSize: "max(14px, 1.3vh)" }}
                        >
                          {tab.label}
                        </span>
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <button
                onClick={signOut}
                className="text-neutral-400 hover:text-neutral-600 transition-colors cursor-pointer"
                style={{ fontSize: "max(14px, 1.3vh)" }}
              >
                Sign out
              </button>
            </div>

            {/* Divider */}
            <div
              className="border-t border-neutral-100"
              style={{ marginBottom: "max(32px, 3vh)" }}
            />

            {/* Tabs */}
            <div
              className="flex"
              style={{ gap: "max(8px, 0.8vh)", marginBottom: "max(32px, 3vh)" }}
            >
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center font-medium rounded-full transition-colors cursor-pointer ${
                    activeTab === tab.key
                      ? "bg-neutral-900 text-white"
                      : "text-neutral-400 hover:text-neutral-600"
                  }`}
                  style={{
                    padding: "max(8px, 0.8vh) max(20px, 1.8vh)",
                    fontSize: "max(14px, 1.4vh)",
                    gap: "max(8px, 0.7vh)",
                  }}
                >
                  {tab.icon}
                  {tab.label}
                  <span className={activeTab === tab.key ? "text-neutral-400" : "text-neutral-300"}>
                    {counts[tab.key]}
                  </span>
                </button>
              ))}
            </div>

            {/* Content */}
            {activeCameras.length === 0 ? (
              <div
                className="bg-neutral-50 rounded-2xl flex flex-col items-center text-center"
                style={{ padding: "max(64px, 6vh) max(24px, 2vh)" }}
              >
                <div className="text-neutral-300" style={{ marginBottom: "max(16px, 1.5vh)" }}>
                  <svg
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    stroke="none"
                    className="mx-auto"
                    style={{ width: "max(48px, 4.5vh)", height: "max(48px, 4.5vh)" }}
                  >
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                  </svg>
                </div>
                <p className="text-neutral-400" style={{ fontSize: "max(14px, 1.4vh)" }}>
                  <Link href="/" className="text-neutral-900 hover:underline">
                    Browse the collection
                  </Link>{" "}
                  and {activeTabDef.emptyText.toLowerCase().split("and ").slice(1).join("and ") || activeTabDef.emptyText.toLowerCase()}
                </p>
              </div>
            ) : (
              <div
                className="grid"
                style={{
                  gridTemplateColumns: "repeat(auto-fill, minmax(max(180px, 14vh), 1fr))",
                  gap: "max(16px, 1.5vh)",
                }}
              >
                {activeCameras.map((c) => (
                  <CameraTile
                    key={c.id}
                    camera={c}
                    hasDetail={!!c.hasDetail}
                    browse
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
