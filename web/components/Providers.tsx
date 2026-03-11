"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/contexts/AuthContext";
import { UserDataProvider } from "@/contexts/UserDataContext";

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <UserDataProvider>{children}</UserDataProvider>
    </AuthProvider>
  );
}
