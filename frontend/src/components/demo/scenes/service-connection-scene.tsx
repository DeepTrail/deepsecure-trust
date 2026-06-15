"use client";

import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DemoSceneProps } from "./types";

const services = [
  { name: "Notion", scopes: ["pages:read", "pages:write"], delay: 0 },
  { name: "Slack", scopes: ["messages:read", "messages:write"], delay: 0.4 },
  { name: "GitHub", scopes: ["repos:read"], delay: 0.8 },
];

export function ServiceConnectionScene({
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
              <CardTitle className="text-lg">Step 2: Connect Services</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Sarah connects Notion, Slack, and GitHub via OAuth. Credentials are
                stored in the vault — never exposed to agents.
              </p>
              <div className="space-y-3">
                {services.map((svc, i) => (
                  <motion.div
                    key={svc.name}
                    className="flex items-center justify-between rounded-md border p-3"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{
                      duration: dur,
                      delay: shouldReduce ? 0 : svc.delay,
                    }}
                    onAnimationComplete={
                      i === services.length - 1 ? onComplete : undefined
                    }
                  >
                    <span className="text-sm font-medium">{svc.name}</span>
                    <div className="flex gap-1">
                      {svc.scopes.map((s) => (
                        <Badge key={s} variant="outline" className="text-xs">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </motion.div>
                ))}
              </div>
              <div className="flex gap-2">
                <Badge>OAuth 2.0</Badge>
                <Badge variant="secondary">Secure Vault Storage</Badge>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
