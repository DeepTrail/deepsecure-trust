import { AlertCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorCardProps {
  title?: string;
  message: string;
  retry?: () => void;
  className?: string;
}

export function ErrorCard({
  title = "Something went wrong",
  message,
  retry,
  className,
}: ErrorCardProps) {
  return (
    <Card
      className={cn("border-destructive/50 bg-destructive/5", className)}
    >
      <CardContent className="flex items-start gap-4 p-6">
        <AlertCircle className="h-5 w-5 shrink-0 text-destructive mt-0.5" />
        <div className="flex-1 space-y-2">
          <p className="font-medium text-destructive">{title}</p>
          <p className="text-sm text-muted-foreground">{message}</p>
          {retry && (
            <Button
              variant="outline"
              size="sm"
              onClick={retry}
              className="mt-2"
            >
              Try again
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
