"use client";

import { useState, useEffect, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

interface TaggedPrompt {
  services: string;
  prompt: string;
  added_by?: string | null;
  index: number;
}

interface PromptEditorProps {
  agentId: string;
  userEmail: string;
  delegatedServices: string[];
  isAdmin?: boolean;
}

export function PromptEditor({
  agentId,
  userEmail,
  delegatedServices,
  isAdmin = false,
}: PromptEditorProps) {
  const [prompts, setPrompts] = useState<TaggedPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newServices, setNewServices] = useState("");
  const [newPrompt, setNewPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [serviceSuggestions, setServiceSuggestions] = useState<string[]>([]);

  const fetchPrompts = useCallback(async () => {
    try {
      const data = await apiClient<{ prompts: TaggedPrompt[]; total: number }>(
        `agents/${agentId}/prompts`
      );
      setPrompts(
        (data.prompts ?? []).map((p, i) => ({ ...p, index: i }))
      );
      setError(null);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `Failed to load prompts (${err.status})`
          : "Failed to load prompts"
      );
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    fetchPrompts();
  }, [fetchPrompts]);

  useEffect(() => {
    setServiceSuggestions(delegatedServices);
  }, [delegatedServices]);

  const handleAdd = async () => {
    if (!newServices.trim() || !newPrompt.trim()) return;
    setSubmitting(true);
    try {
      await apiClient(`agents/${agentId}/prompts`, {
        method: "POST",
        body: JSON.stringify({
          services: newServices.trim(),
          prompt: newPrompt.trim(),
        }),
      });
      setNewServices("");
      setNewPrompt("");
      setShowAdd(false);
      await fetchPrompts();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to add prompt"
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (index: number) => {
    try {
      await apiClient(`agents/${agentId}/prompts/${index}`, {
        method: "DELETE",
      });
      await fetchPrompts();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to delete prompt"
      );
    }
  };

  const canDelete = (prompt: TaggedPrompt) =>
    isAdmin || prompt.added_by === userEmail;

  const isOwnPrompt = (prompt: TaggedPrompt) =>
    prompt.added_by === userEmail;

  const adminPrompts = prompts.filter(
    (p) => p.added_by && p.added_by !== userEmail && !isAdmin
  );
  const myPrompts = prompts.filter(
    (p) => isOwnPrompt(p) || isAdmin
  );

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg bg-muted"
          />
        ))}
      </div>
    );
  }

  const filteredSuggestions = serviceSuggestions.filter(
    (s) =>
      s.toLowerCase().includes(newServices.split(",").pop()?.trim().toLowerCase() ?? "")
  );

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-200">
          {error}
        </div>
      )}

      {/* Admin prompts (read-only for non-admin) */}
      {!isAdmin && adminPrompts.length > 0 && (
        <div className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Lock className="h-3.5 w-3.5" />
            Admin Prompts (read-only)
          </h3>
          {adminPrompts.map((prompt) => (
            <Card
              key={`admin-${prompt.index}`}
              className="bg-muted/30 p-4"
            >
              <div className="flex items-start gap-2">
                <div className="flex-1 space-y-1.5">
                  <div className="flex flex-wrap gap-1">
                    {prompt.services.split(",").map((s) => (
                      <Badge key={s} variant="secondary" className="text-xs">
                        {s.trim()}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-sm">{prompt.prompt}</p>
                  <p className="text-xs text-muted-foreground">
                    Added by: {prompt.added_by}
                  </p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* User's prompts (or all prompts for admin) */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">
          {isAdmin ? "All Prompts" : "Your Prompts"}
        </h3>
        {myPrompts.length === 0 && !showAdd && (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No prompts yet. Add one to tell the agent what to do.
          </p>
        )}
        {myPrompts.map((prompt) => (
          <Card key={`my-${prompt.index}`} className="p-4">
            <div className="flex items-start gap-2">
              <div className="flex-1 space-y-1.5">
                <div className="flex flex-wrap gap-1">
                  {prompt.services.split(",").map((s) => (
                    <Badge key={s} variant="outline" className="text-xs">
                      {s.trim()}
                    </Badge>
                  ))}
                </div>
                <p className="text-sm">{prompt.prompt}</p>
                {prompt.added_by && (
                  <p className="text-xs text-muted-foreground">
                    Added by: {isOwnPrompt(prompt) ? "you" : prompt.added_by}
                  </p>
                )}
              </div>
              {canDelete(prompt) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(prompt.index)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>

      {/* Add prompt form */}
      {showAdd ? (
        <Card className="border-dashed p-4">
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium">
                Services
              </label>
              <Input
                placeholder="Type service name (e.g., notion, slack)"
                value={newServices}
                onChange={(e) => setNewServices(e.target.value)}
              />
              {filteredSuggestions.length > 0 && newServices && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {filteredSuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => {
                        const parts = newServices.split(",");
                        parts[parts.length - 1] = s;
                        setNewServices(parts.join(","));
                      }}
                      className={cn(
                        "rounded-md border px-2 py-0.5 text-xs transition-colors",
                        "hover:bg-primary hover:text-primary-foreground"
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                Prompt
              </label>
              <textarea
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 resize-y"
                placeholder="What should the agent do with this service?"
                value={newPrompt}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNewPrompt(e.target.value)}
                rows={3}
              />
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={handleAdd}
                disabled={submitting || !newServices.trim() || !newPrompt.trim()}
              >
                {submitting ? "Adding..." : "Add Prompt"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAdd(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </Card>
      ) : (
        <Button variant="outline" size="sm" onClick={() => setShowAdd(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Prompt
        </Button>
      )}
    </div>
  );
}
