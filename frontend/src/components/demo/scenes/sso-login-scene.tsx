"use client";

import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DemoSceneProps } from "./types";

const steps = [
  { label: "User", delay: 0 },
  { label: "IdP (Keycloak)", delay: 0.4 },
  { label: "JWT Issued", delay: 0.8 },
  { label: "Dashboard", delay: 1.2 },
];

export function SsoLoginScene({ isActive, onComplete, className }: DemoSceneProps) {
  const shouldReduce = useReducedMotion();
  const duration = shouldReduce ? 0 : 0.5;

  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration }}
          className={className}
        >
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Step 1: SSO Authentication</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Sarah signs in via Keycloak SSO. Her identity is verified and a JWT is
                issued with her groups and roles.
              </p>
              <div className="flex gap-2">
                <Badge>Keycloak</Badge>
                <Badge variant="outline">JWT Issued</Badge>
                <Badge variant="secondary">L2 User Token</Badge>
              </div>
              <div className="flex items-center gap-2">
                {steps.map((step, i) => (
                  <motion.div
                    key={step.label}
                    className="flex-1 rounded-md bg-primary/10 p-2 text-center text-xs font-medium"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{
                      duration: shouldReduce ? 0 : 0.3,
                      delay: shouldReduce ? 0 : step.delay,
                    }}
                    onAnimationComplete={
                      i === steps.length - 1 ? onComplete : undefined
                    }
                  >
                    {step.label}
                  </motion.div>
                ))}
              </div>
              <motion.div
                className="h-2 rounded-full bg-primary"
                initial={{ width: 0 }}
                animate={{ width: "100%" }}
                transition={{ duration: shouldReduce ? 0 : 1.5, delay: shouldReduce ? 0 : 0.3 }}
              />
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
