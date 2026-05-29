"use client";

import { useRouter } from "next/navigation";
import { useUserRole } from "@/hooks/useUserRole";
import { PageSkeleton } from "@/components/feedback";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { isAdmin, isLoading } = useUserRole();
  const router = useRouter();

  if (isLoading) {
    return <PageSkeleton />;
  }

  if (!isAdmin) {
    router.replace("/dashboard");
    return null;
  }

  return <>{children}</>;
}
