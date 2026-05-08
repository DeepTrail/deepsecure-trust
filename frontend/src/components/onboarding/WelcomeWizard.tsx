"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StepIndicator, type Step } from "./StepIndicator";
import { completeOnboarding } from "@/lib/auth/onboarding";
import { ApiError } from "@/lib/api/client";
import {
  Shield,
  Plug,
  Bot,
  KeyRound,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
} from "lucide-react";

const STEPS: Step[] = [
  { id: "welcome", label: "Welcome" },
  { id: "connect-service", label: "Connect Service" },
  { id: "register-agent", label: "Register Agent" },
  { id: "create-delegation", label: "Create Delegation" },
  { id: "complete", label: "Complete" },
];

interface WelcomeWizardProps {
  onComplete?: () => void;
}

export function WelcomeWizard({ onComplete }: WelcomeWizardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const goNext = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep((s) => s + 1);
      setError(null);
    }
  };

  const goBack = () => {
    if (currentStep > 0) {
      setCurrentStep((s) => s - 1);
      setError(null);
    }
  };

  const handleComplete = async () => {
    setCompleting(true);
    setError(null);
    try {
      await completeOnboarding();
      onComplete?.();
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to complete onboarding (${err.status})`
          : "Failed to complete onboarding. Please try again.";
      setError(message);
      setCompleting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <StepIndicator steps={STEPS} currentStep={currentStep} />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {currentStep === 0 && <Shield className="h-5 w-5" />}
            {currentStep === 1 && <Plug className="h-5 w-5" />}
            {currentStep === 2 && <Bot className="h-5 w-5" />}
            {currentStep === 3 && <KeyRound className="h-5 w-5" />}
            {currentStep === 4 && <CheckCircle2 className="h-5 w-5 text-green-600" />}
            {STEPS[currentStep].label}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {currentStep === 0 && <WelcomeContent />}
          {currentStep === 1 && <ConnectServiceContent />}
          {currentStep === 2 && <RegisterAgentContent />}
          {currentStep === 3 && <CreateDelegationContent />}
          {currentStep === 4 && <CompleteContent />}

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <div className="flex justify-between pt-4">
            <Button
              variant="ghost"
              onClick={goBack}
              disabled={currentStep === 0}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>

            {currentStep < STEPS.length - 1 ? (
              <Button onClick={goNext}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={handleComplete} disabled={completing}>
                {completing ? "Finishing..." : "Go to Dashboard"}
                {!completing && <ArrowRight className="ml-2 h-4 w-4" />}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function WelcomeContent() {
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground">
        Welcome to DeepSecure! This wizard will guide you through setting up
        identity-based security for your AI agents.
      </p>
      <div className="rounded-lg border p-4 space-y-2">
        <h4 className="font-medium">The DeepSecure Trust Model</h4>
        <ul className="space-y-1 text-sm text-muted-foreground list-disc pl-4">
          <li>Agents authenticate with Ed25519 cryptographic keys</li>
          <li>Delegations grant scoped permissions from users to agents</li>
          <li>Secrets are injected at runtime — never stored in code</li>
          <li>Every action is logged in an immutable audit trail</li>
        </ul>
      </div>
    </div>
  );
}

function ConnectServiceContent() {
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground">
        Connect an external service that your agent will access. DeepSecure
        handles OAuth flows and securely stores credentials.
      </p>
      <div className="rounded-lg border p-4 space-y-2">
        <h4 className="font-medium">Supported Services</h4>
        <p className="text-sm text-muted-foreground">
          Notion, Slack, GitHub, and more. You can connect additional services
          later from the Services page.
        </p>
      </div>
      <p className="text-xs text-muted-foreground">
        You can skip this step and connect services later.
      </p>
    </div>
  );
}

function RegisterAgentContent() {
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground">
        Register an AI agent with a unique identity. The agent will use an
        Ed25519 keypair to authenticate with DeepSecure services.
      </p>
      <div className="rounded-lg border p-4 space-y-2">
        <h4 className="font-medium">Agent Identity</h4>
        <p className="text-sm text-muted-foreground">
          Each agent gets a unique ID, a cryptographic keypair, and can be
          associated with multiple delegations. You can register agents later
          from the Agents page.
        </p>
      </div>
    </div>
  );
}

function CreateDelegationContent() {
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground">
        Create a delegation to grant specific permissions from your account to
        an agent. Delegations define exactly which actions an agent can perform.
      </p>
      <div className="rounded-lg border p-4 space-y-2">
        <h4 className="font-medium">Scoped Permissions</h4>
        <p className="text-sm text-muted-foreground">
          Permissions follow the pattern{" "}
          <code className="rounded bg-muted px-1">service:scope:action</code>.
          For example, <code className="rounded bg-muted px-1">notion:pages:read</code>{" "}
          grants read access to Notion pages only.
        </p>
      </div>
    </div>
  );
}

function CompleteContent() {
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground">
        You&apos;re all set! Your DeepSecure environment is ready. You can
        always adjust settings, add more agents, or connect new services from
        the dashboard.
      </p>
      <div className="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-900 dark:bg-green-950">
        <p className="text-sm font-medium text-green-800 dark:text-green-200">
          Click &quot;Go to Dashboard&quot; to complete onboarding and start
          using DeepSecure.
        </p>
      </div>
    </div>
  );
}
