"use client";

import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DemoSceneProps } from "./types";

const toolCalls = [
  {
    tool: "notion.search_pages",
    args: 'query: "Q4 planning"',
    result: "success",
    detail: "3 pages found",
    delay: 0,
  },
  {
    tool: "slack.post_message",
    args: 'channel: "#research"',
    result: "success",
    detail: "Message sent",
    delay: 0.6,
  },
  {
    tool: "gmail.list_messages",
    args: "{}",
    result: "denied",
    detail: "gmail:messages:read not delegated",
    delay: 1.2,
  },
];

export function McpToolCallScene({
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
              <CardTitle className="text-lg">Step 5: MCP Tool Execution</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                The agent calls tools through the MCP gateway. Each call is authorized
                against the delegation. Undelegated tools are denied.
              </p>
              <div className="space-y-3">
                {toolCalls.map((call, i) => (
                  <motion.div
                    key={call.tool}
                    className={`flex items-center justify-between rounded-md border p-3 ${
                      call.result === "denied"
                        ? "border-destructive/50 bg-destructive/5"
                        : "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950"
                    }`}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{
                      duration: dur,
                      delay: shouldReduce ? 0 : call.delay,
                    }}
                    onAnimationComplete={
                      i === toolCalls.length - 1 ? onComplete : undefined
                    }
                  >
                    <div>
                      <span className="text-sm font-mono font-medium">
                        {call.tool}
                      </span>
                      <p className="text-xs text-muted-foreground">{call.args}</p>
                    </div>
                    <Badge
                      variant={
                        call.result === "success" ? "default" : "destructive"
                      }
                    >
                      {call.result === "success" ? call.detail : "Denied"}
                    </Badge>
                  </motion.div>
                ))}
              </div>
              <div className="flex gap-2">
                <Badge>MCP Protocol</Badge>
                <Badge variant="secondary">Secret Injection</Badge>
                <Badge variant="outline">Permission Enforcement</Badge>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
