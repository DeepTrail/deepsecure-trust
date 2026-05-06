import { Metadata } from "next";
import { Shield } from "lucide-react";
import Link from "next/link";
import { SceneManager } from "@/components/demo/scene-manager";

export const dynamic = "force-static";

export const metadata: Metadata = {
  title: "DeepSecure Interactive Demo",
  description:
    "See how DeepSecure manages AI agent identity, delegation, and audit in real-time.",
};

export default function DemoPage() {
  return (
    <main className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <span className="text-lg font-semibold">DeepSecure Demo</span>
        </div>
        <Link
          href="/login"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Try DeepSecure
        </Link>
      </header>

      {/* Scene Manager */}
      <div className="flex-1 p-6 md:p-10 max-w-7xl mx-auto w-full">
        <SceneManager />
      </div>

      {/* Footer */}
      <footer className="border-t px-6 py-4 text-center text-sm text-muted-foreground">
        <p>
          <Link href="/login" className="underline hover:text-foreground">
            Get started with DeepSecure
          </Link>{" "}
          — Identity-as-Code for AI agents
        </p>
        <p className="mt-1">&copy; {new Date().getFullYear()} DeepSecure</p>
      </footer>
    </main>
  );
}
