"use client";

import { UserProvider } from "@/lib/useUserId";
import type { ReactNode } from "react";

export default function Providers({ children }: { children: ReactNode }) {
  return <UserProvider>{children}</UserProvider>;
}
