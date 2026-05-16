"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { WelcomeWizard } from "@/components/onboarding";
import { checkOnboardingStatus } from "@/lib/auth/onboarding";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { ApiError } from "@/lib/api/client";

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready" }
  | { kind: "already-completed" };

export default function OnboardingPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const router = useRouter();

  const checkStatus = async () => {
    setState({ kind: "loading" });
    try {
      const destination = await checkOnboardingStatus();
      if (destination === "dashboard") {
        setState({ kind: "already-completed" });
        router.replace("/dashboard");
      } else {
        setState({ kind: "ready" });
      }
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to check onboarding status (${err.status})`
          : "Failed to load onboarding. Please try again.";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    checkStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleComplete = () => {
    router.replace("/dashboard");
  };

  if (state.kind === "loading" || state.kind === "already-completed") {
    return <PageSkeleton />;
  }

  if (state.kind === "error") {
    return (
      <ErrorCard
        title="Onboarding"
        message={state.message}
        retry={checkStatus}
      />
    );
  }

  return (
    <div className="py-8">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold">Get Started with DeepSecure</h1>
        <p className="mt-2 text-muted-foreground">
          Follow these steps to set up a trust layer for your AI agents.
        </p>
      </div>
      <WelcomeWizard onComplete={handleComplete} />
    </div>
  );
}
