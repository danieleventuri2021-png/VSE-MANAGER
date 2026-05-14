import { badgeClass } from "../lib/status";
import type React from "react";

export function Badge({ children, status }: { children: React.ReactNode; status: string }) {
  return <span className={`inline-flex items-center rounded border px-2 py-1 text-xs font-medium ${badgeClass(status)}`}>{children}</span>;
}
