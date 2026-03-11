"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useUserData } from "@/contexts/UserDataContext";

export default function CollectionButtons({ cameraId }: { cameraId: string }) {
  const { user, signIn } = useAuth();
  const { owned, favorites, wishlist, toggleOwn, toggleFavorite, toggleWishlist } = useUserData();

  const isOwned = owned.has(cameraId);
  const isFavorite = favorites.has(cameraId);
  const isWishlist = wishlist.has(cameraId);

  const handle = (action: () => void) => {
    if (!user) {
      signIn();
      return;
    }
    action();
  };

  return (
    <div className="flex gap-2 mt-4">
      <button
        onClick={() => handle(() => toggleFavorite(cameraId))}
        className={`flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-full border transition-colors cursor-pointer ${
          isFavorite
            ? "bg-neutral-900 text-white border-neutral-900"
            : "text-neutral-600 border-neutral-200 hover:bg-neutral-50"
        }`}
      >
        <svg
          className="w-4 h-4"
          viewBox="0 0 24 24"
          fill={isFavorite ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth={isFavorite ? 0 : 2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
        Favorite
      </button>

      <button
        onClick={() => handle(() => toggleOwn(cameraId))}
        className={`flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-full border transition-colors cursor-pointer ${
          isOwned
            ? "bg-neutral-900 text-white border-neutral-900"
            : "text-neutral-600 border-neutral-200 hover:bg-neutral-50"
        }`}
      >
        <svg
          className="w-4 h-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
        Owned
      </button>

      <button
        onClick={() => handle(() => toggleWishlist(cameraId))}
        className={`flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-full border transition-colors cursor-pointer ${
          isWishlist
            ? "bg-neutral-900 text-white border-neutral-900"
            : "text-neutral-600 border-neutral-200 hover:bg-neutral-50"
        }`}
      >
        <svg
          className="w-4 h-4"
          viewBox="0 0 24 24"
          fill={isWishlist ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth={isWishlist ? 0 : 2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
        Wishlist
      </button>
    </div>
  );
}
