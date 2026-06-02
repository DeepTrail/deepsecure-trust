"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

interface TTLSelectorProps {
  value: number;
  onChange: (value: number) => void;
  unit?: "minutes" | "days";
}

const MINUTES_OPTIONS = [
  { label: "15 min", value: 15 },
  { label: "1 hour", value: 60 },
  { label: "8 hours", value: 480 },
  { label: "24 hours", value: 1440 },
  { label: "7 days", value: 10080 },
];

const DAYS_OPTIONS = [
  { label: "1 day", value: 1 },
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
];

export function TTLSelector({ value, onChange, unit = "minutes" }: TTLSelectorProps) {
  const [showCustom, setShowCustom] = useState(false);
  const options = unit === "days" ? DAYS_OPTIONS : MINUTES_OPTIONS;
  const isPreset = options.some((o) => o.value === value);

  function handleCustom() {
    setShowCustom(true);
  }

  function handlePreset(v: number) {
    setShowCustom(false);
    onChange(v);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => handlePreset(option.value)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
              value === option.value && !showCustom
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:border-foreground hover:text-foreground"
            )}
          >
            {option.label}
          </button>
        ))}
        <button
          type="button"
          onClick={handleCustom}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            (showCustom || (!isPreset && value > 0))
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border text-muted-foreground hover:border-foreground hover:text-foreground"
          )}
        >
          Custom
        </button>
      </div>
      {(showCustom || (!isPreset && value > 0)) && (
        <div className="flex items-center gap-2">
          <Input
            type="number"
            min={1}
            value={value}
            onChange={(e) => onChange(parseInt(e.target.value, 10) || 1)}
            className="w-24"
          />
          <span className="text-sm text-muted-foreground">{unit}</span>
        </div>
      )}
    </div>
  );
}
