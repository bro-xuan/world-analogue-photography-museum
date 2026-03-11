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
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" stroke="none">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    ),
    emptyText: "Browse the collection and favorite what you want to remember.",
  },
  {
    key: "owned",
    label: "Owned",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    ),
    emptyText: "Mark cameras you own to build your collection.",
  },
  {
    key: "wishlist",
    label: "Wishlist",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
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
      <main className="max-w-4xl mx-auto px-6 pt-10 pb-16">
        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-900 rounded-full animate-spin" />
          </div>
        ) : !user ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <h1 className="font-display text-2xl font-bold text-neutral-900 mb-2">
              My Collection
            </h1>
            <p className="text-neutral-400 mb-6">
              Sign in to start tracking cameras you own and your favorites.
            </p>
            <button
              onClick={signIn}
              className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-neutral-700 border border-neutral-200 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer"
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
            <div className="flex items-start justify-between mb-8">
              <div className="flex items-center gap-5">
                {user.photoURL ? (
                  <img
                    src={user.photoURL}
                    alt=""
                    className="w-20 h-20 rounded-full"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="w-20 h-20 rounded-full bg-neutral-200 flex items-center justify-center text-2xl font-medium text-neutral-600">
                    {(user.displayName || user.email || "?")[0].toUpperCase()}
                  </div>
                )}
                <div>
                  <h1 className="font-display text-xl font-bold text-neutral-900">
                    {user.displayName}
                  </h1>
                  {/* Stats row */}
                  <div className="flex items-center gap-4 mt-2">
                    {TABS.map((tab, i) => (
                      <span key={tab.key} className="flex items-center gap-1">
                        {i > 0 && <span className="text-neutral-200 mr-3">|</span>}
                        <span className="text-base font-semibold text-neutral-900">
                          {counts[tab.key]}
                        </span>
                        <span className="text-sm text-neutral-400">{tab.label}</span>
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <button
                onClick={signOut}
                className="text-sm text-neutral-400 hover:text-neutral-600 transition-colors cursor-pointer"
              >
                Sign out
              </button>
            </div>

            {/* Divider */}
            <div className="border-t border-neutral-100 mb-8" />

            {/* Tabs */}
            <div className="flex gap-2 mb-8">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-full transition-colors cursor-pointer ${
                    activeTab === tab.key
                      ? "bg-neutral-900 text-white"
                      : "text-neutral-400 hover:text-neutral-600"
                  }`}
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
              <div className="bg-neutral-50 rounded-2xl py-16 flex flex-col items-center text-center">
                <div className="text-neutral-300 mb-4">
                  <svg className="w-12 h-12 mx-auto" viewBox="0 0 24 24" fill="currentColor" stroke="none">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                  </svg>
                </div>
                <p className="text-sm text-neutral-400">
                  <Link href="/" className="text-neutral-900 hover:underline">
                    Browse the collection
                  </Link>{" "}
                  and {activeTabDef.emptyText.toLowerCase().split("and ").slice(1).join("and ") || activeTabDef.emptyText.toLowerCase()}
                </p>
              </div>
            ) : (
              <div
                className="grid gap-4"
                style={{
                  gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
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
