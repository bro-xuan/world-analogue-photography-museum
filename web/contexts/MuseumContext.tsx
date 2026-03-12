"use client";

import { createContext, useContext, useRef, useCallback } from "react";

type MuseumContextType = {
  registerLeaveBrowse: (fn: () => void) => void;
  triggerLeaveBrowse: () => void;
};

const MuseumContext = createContext<MuseumContextType>({
  registerLeaveBrowse: () => {},
  triggerLeaveBrowse: () => {},
});

export function MuseumProvider({ children }: { children: React.ReactNode }) {
  const leaveBrowseRef = useRef<(() => void) | null>(null);

  const registerLeaveBrowse = useCallback((fn: () => void) => {
    leaveBrowseRef.current = fn;
  }, []);

  const triggerLeaveBrowse = useCallback(() => {
    leaveBrowseRef.current?.();
  }, []);

  return (
    <MuseumContext.Provider value={{ registerLeaveBrowse, triggerLeaveBrowse }}>
      {children}
    </MuseumContext.Provider>
  );
}

export function useMuseum() {
  return useContext(MuseumContext);
}
