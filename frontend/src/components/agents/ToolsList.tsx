import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, Wrench } from "lucide-react";

export interface AgentTool {
  name: string;
  backend: string;
  permission: string;
  available: boolean;
  reason?: string;
}

interface ToolsListProps {
  tools: AgentTool[];
}

export function ToolsList({ tools }: ToolsListProps) {
  if (tools.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          <Wrench className="mx-auto mb-2 h-8 w-8" />
          No tools configured for this agent.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Wrench className="h-4 w-4 text-muted-foreground" />
          Tools ({tools.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {tools.map((tool) => (
          <div
            key={tool.name}
            className="flex items-center justify-between rounded-lg border p-3"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                {tool.available ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-500" />
                )}
                <span className="text-sm font-medium font-mono">
                  {tool.name}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {tool.permission}
              </p>
              {!tool.available && tool.reason && (
                <p className="text-xs text-destructive">{tool.reason}</p>
              )}
            </div>
            <Badge variant={tool.available ? "default" : "secondary"}>
              {tool.backend}
            </Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
