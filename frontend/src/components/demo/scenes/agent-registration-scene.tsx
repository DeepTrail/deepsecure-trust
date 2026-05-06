"use client";

import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DemoSceneProps } from "./types";

const steps = [
  { label: "Generate Ed25519 Keypair", delay: 0 },
  { label: "Register Public Key", delay: 0.5 },
  { label: "Challenge-Response", delay: 1.0 },
  { label: "Agent Verified ✓", delay: 1.5 },
];

export function AgentRegistrationScene({
  isActive,
  onComplete,
  className,
}: DemoSceneProps) {
  const shouldReduce = useReducedMotion();
  const dur = shouldReduce ? 0 : 0.4;

  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: dur }}
          className={className}
        >
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Step 3: Register Agent</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                An Ed25519 keypair is generated. The agent registers its public key and
                proves identity via cryptographic challenge-response.
              </p>
              <div className="space-y-2">
                {steps.map((step, i) => (
                  <motion.div
                    key={step.label}
                    className="flex items-center gap-3 rounded-md border p-2"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{
                      duration: dur,
                      delay: shouldReduce ? 0 : step.delay,
                    }}
                    onAnimationComplete={
                      i === steps.length - 1 ? onComplete : undefined
                    }
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium">
                      {i + 1}
                    </span>
                    <span className="text-sm">{step.label}</span>
                  </motion.div>
                ))}
              </div>
              <div className="flex gap-2">
                <Badge>Ed25519</Badge>
                <Badge variant="outline">Challenge-Response</Badge>
                <Badge variant="secondary">Agent Identity</Badge>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
