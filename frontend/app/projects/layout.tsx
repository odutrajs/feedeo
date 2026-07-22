"use client";

import { RequireAuth } from "@/lib/auth";

export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
