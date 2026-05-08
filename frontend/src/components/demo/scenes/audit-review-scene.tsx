"use client";

import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DemoSceneProps } from "./types";

const events = [
  { time: "09:01", event: "SSO Login", actor: "sarah@acme.com", layer: "L2", delay: 0 },
  { time: "09:02", event: "Delegation Created", actor: "sarah@acme.com", layer: "L2", delay: 0.3 },
  { time: "09:03", event: "Agent Authenticated", actor: "sarah-research-agent", layer: "L3", delay: 0.6 },
  { time: "09:04", event: "notion.search_pages", actor: "sarah-research-agent", layer: "L3", delay: 0.9 },
  { time: "09:05", event: "Permission Denied", actor: "sarah-research-agent", layer: "L3", delay: 1.2 },
];

const layerColors: Record<string, string> = {
  L2: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  L3: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

export function AuditReviewScene({
  isActive,
  onComplete,
  className,
}: DemoSceneProps) {
  const shouldReduce = useReducedMotion();
  const dur = shouldReduce ? 0 : 0.3;

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
              <CardTitle className="text-lg">Step 6: Audit Review</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Every action is logged with full attribution chain — who delegated,
                which agent acted, what was accessed, and the outcome.
              </p>
              <div className="space-y-2">
                {events.map((evt, i) => (
                  <motion.div
                    key={evt.time + evt.event}
                    className="flex items-center justify-between rounded-md border p-2 text-sm"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: dur,
                      delay: shouldReduce ? 0 : evt.delay,
                    }}
                    onAnimationComplete={
                      i === events.length - 1 ? onComplete : undefined
                    }
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground font-mono">
                        {evt.time}
                      </span>
                      <span className="font-medium">{evt.event}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {evt.actor}
                      </span>
                      <Badge className={layerColors[evt.layer] ?? ""}>
                        {evt.layer}
                      </Badge>
                    </div>
                  </motion.div>
                ))}
              </div>
              <div className="flex gap-2">
                <Badge>Full Attribution</Badge>
                <Badge variant="secondary">Token Layer Tracking</Badge>
                <Badge variant="outline">Denial Logging</Badge>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
