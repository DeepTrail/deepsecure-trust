"use client";

import { ErrorCard } from "@/components/feedback";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex items-center justify-center p-8">
      <ErrorCard
        title="Dashboard Error"
        message={error.message || "Failed to load dashboard content"}
        retry={reset}
      />
    </div>
  );
}
