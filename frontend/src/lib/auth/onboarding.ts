import { apiClient } from "@/lib/api/client";

interface UserProfile {
  id: string;
  email: string;
  onboarding_completed: boolean;
}

export type OnboardingDestination = "onboarding" | "dashboard";

export async function checkOnboardingStatus(): Promise<OnboardingDestination> {
  const user = await apiClient<UserProfile>("users/me");
  return user.onboarding_completed ? "dashboard" : "onboarding";
}

export async function completeOnboarding(): Promise<void> {
  await apiClient("users/me", {
    method: "PATCH",
    body: JSON.stringify({ onboarding_completed: true }),
  });
}
