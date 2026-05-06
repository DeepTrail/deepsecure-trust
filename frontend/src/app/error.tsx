"use client";

import { ErrorCard } from "@/components/feedback";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center p-8">
      <ErrorCard
        title="Application Error"
        message={error.message || "An unexpected error occurred"}
        retry={reset}
      />
    </div>
  );
}
