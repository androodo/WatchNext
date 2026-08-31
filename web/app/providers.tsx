"use client";

import { UserProvider } from "@/lib/useUserId";
import TicketResetDialog from "@/components/TicketResetDialog";
import KeyboardNav from "@/components/KeyboardNav";
import type { ReactNode } from "react";

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <UserProvider>
      <KeyboardNav />
      {children}
      <TicketResetDialog />
    </UserProvider>
  );
}
