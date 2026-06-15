"use client";

import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DemoSceneProps } from "./types";

const permissions = [
  "notion:pages:read",
  "notion:pages:write",
  "slack:messages:search",
  "slack:messages:write",
];

export function DelegationScene({
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
              <CardTitle className="text-lg">Step 4: Delegate Permissions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Sarah delegates specific, scoped permissions to her agent. The agent
                can only access what Sarah explicitly allows.
              </p>
              <div className="flex flex-wrap gap-2">
                {permissions.map((perm, i) => (
                  <motion.div
                    key={perm}
                    initial={{ opacity: 0, scale: 0.5 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{
                      duration: shouldReduce ? 0 : 0.3,
                      delay: shouldReduce ? 0 : i * 0.3,
                    }}
                    onAnimationComplete={
                      i === permissions.length - 1 ? onComplete : undefined
                    }
                  >
                    <Badge variant="outline" className="font-mono text-xs">
                      {perm}
                    </Badge>
                  </motion.div>
                ))}
              </div>
              <div className="flex gap-2">
                <Badge>Scoped Delegation</Badge>
                <Badge variant="secondary">L3 Agent Token</Badge>
                <Badge variant="outline">Least Privilege</Badge>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
