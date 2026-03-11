"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import {
  doc,
  getDoc,
  setDoc,
  updateDoc,
  arrayUnion,
  arrayRemove,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useAuth } from "./AuthContext";

interface UserDataContextValue {
  owned: Set<string>;
  favorites: Set<string>;
  wishlist: Set<string>;
  toggleOwn: (id: string) => void;
  toggleFavorite: (id: string) => void;
  toggleWishlist: (id: string) => void;
}

const UserDataContext = createContext<UserDataContextValue>({
  owned: new Set(),
  favorites: new Set(),
  wishlist: new Set(),
  toggleOwn: () => {},
  toggleFavorite: () => {},
  toggleWishlist: () => {},
});

export function UserDataProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [owned, setOwned] = useState<Set<string>>(new Set());
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [wishlist, setWishlist] = useState<Set<string>>(new Set());

  // Fetch or create user doc on sign-in
  useEffect(() => {
    if (!user) {
      setOwned(new Set());
      setFavorites(new Set());
      setWishlist(new Set());
      return;
    }

    const ref = doc(db, "users", user.uid);
    getDoc(ref).then((snap) => {
      if (snap.exists()) {
        const data = snap.data();
        setOwned(new Set(data.owned || []));
        setFavorites(new Set(data.favorites || []));
        setWishlist(new Set(data.wishlist || []));
      } else {
        // Create initial doc
        setDoc(ref, {
          displayName: user.displayName || "",
          email: user.email || "",
          photoURL: user.photoURL || "",
          createdAt: new Date(),
          owned: [],
          favorites: [],
          wishlist: [],
        });
        setOwned(new Set());
        setFavorites(new Set());
        setWishlist(new Set());
      }
    });
  }, [user]);

  const toggleOwn = useCallback(
    (id: string) => {
      if (!user) return;
      const ref = doc(db, "users", user.uid);
      const has = owned.has(id);

      // Optimistic update
      setOwned((prev) => {
        const next = new Set(prev);
        if (has) next.delete(id);
        else next.add(id);
        return next;
      });

      updateDoc(ref, {
        owned: has ? arrayRemove(id) : arrayUnion(id),
      });
    },
    [user, owned]
  );

  const toggleFavorite = useCallback(
    (id: string) => {
      if (!user) return;
      const ref = doc(db, "users", user.uid);
      const has = favorites.has(id);

      // Optimistic update
      setFavorites((prev) => {
        const next = new Set(prev);
        if (has) next.delete(id);
        else next.add(id);
        return next;
      });

      updateDoc(ref, {
        favorites: has ? arrayRemove(id) : arrayUnion(id),
      });
    },
    [user, favorites]
  );

  const toggleWishlist = useCallback(
    (id: string) => {
      if (!user) return;
      const ref = doc(db, "users", user.uid);
      const has = wishlist.has(id);

      setWishlist((prev) => {
        const next = new Set(prev);
        if (has) next.delete(id);
        else next.add(id);
        return next;
      });

      updateDoc(ref, {
        wishlist: has ? arrayRemove(id) : arrayUnion(id),
      });
    },
    [user, wishlist]
  );

  return (
    <UserDataContext.Provider value={{ owned, favorites, wishlist, toggleOwn, toggleFavorite, toggleWishlist }}>
      {children}
    </UserDataContext.Provider>
  );
}

export function useUserData() {
  return useContext(UserDataContext);
}
