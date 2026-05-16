"use client";

import { KeyRound, Cloud, Box } from "lucide-react";
import { cn } from "@/lib/utils";

export type IdentityMethod = "key" | "gcp" | "aws" | "k8s";

interface IdentityMethodSelectorProps {
  value: IdentityMethod;
  onChange: (method: IdentityMethod) => void;
}

const IDENTITY_METHODS: {
  method: IdentityMethod;
  label: string;
  description: string;
  icon: typeof KeyRound;
}[] = [
  {
    method: "key",
    label: "Cryptographic Key",
    description: "Ed25519 keypair — server generates or you provide",
    icon: KeyRound,
  },
  {
    method: "gcp",
    label: "GCP Workload Identity",
    description: "Auto-authenticate via Google Cloud service account",
    icon: Cloud,
  },
  {
    method: "aws",
    label: "AWS IAM",
    description: "Authenticate via AWS IAM Role",
    icon: Cloud,
  },
  {
    method: "k8s",
    label: "Kubernetes",
    description: "Authenticate via K8s Service Account",
    icon: Box,
  },
];

export function IdentityMethodSelector({ value, onChange }: IdentityMethodSelectorProps) {
  return (
    <div
      className="grid grid-cols-1 gap-3 sm:grid-cols-2"
      role="radiogroup"
      aria-label="Identity method"
    >
      {IDENTITY_METHODS.map(({ method, label, description, icon: Icon }) => {
        const selected = value === method;
        return (
          <button
            key={method}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(method)}
            className={cn(
              "flex flex-col items-start gap-2 rounded-lg border-2 p-4 text-left transition-colors",
              selected
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground/30"
            )}
          >
            <div className="flex items-center gap-2">
              <Icon className={cn("h-5 w-5", selected ? "text-primary" : "text-muted-foreground")} />
              <span className={cn("text-sm font-semibold", selected ? "text-primary" : "text-foreground")}>
                {label}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{description}</p>
          </button>
        );
      })}
    </div>
  );
}
