"use client";

import { ErrorCard } from "@/components/feedback";

export default function AuthError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <ErrorCard
        title="Authentication Error"
        message={error.message || "Something went wrong during authentication"}
        retry={reset}
      />
    </div>
  );
}
