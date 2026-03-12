"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/contexts/AuthContext";
import { UserDataProvider } from "@/contexts/UserDataContext";
import { MuseumProvider } from "@/contexts/MuseumContext";

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <UserDataProvider>
        <MuseumProvider>{children}</MuseumProvider>
      </UserDataProvider>
    </AuthProvider>
  );
}
