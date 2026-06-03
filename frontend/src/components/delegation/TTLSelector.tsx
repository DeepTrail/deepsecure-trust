"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

interface TTLSelectorProps {
  value: number;
  onChange: (value: number) => void;
  unit?: "minutes" | "days";
  maxDays?: number;
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

export function TTLSelector({ value, onChange, unit = "minutes", maxDays }: TTLSelectorProps) {
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

  const customMax = maxDays != null && unit === "days" ? maxDays : undefined;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {options.map((option) => {
          const exceedsMax = maxDays != null && unit === "days" && option.value > maxDays;
          return (
            <button
              key={option.value}
              type="button"
              disabled={exceedsMax}
              onClick={() => handlePreset(option.value)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                exceedsMax
                  ? "border-border text-muted-foreground/40 cursor-not-allowed line-through"
                  : value === option.value && !showCustom
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border text-muted-foreground hover:border-foreground hover:text-foreground"
              )}
            >
              {option.label}
            </button>
          );
        })}
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
        {maxDays != null && (
          <span className="text-xs text-muted-foreground">Max: {maxDays}d per template</span>
        )}
      </div>
      {(showCustom || (!isPreset && value > 0)) && (
        <div className="flex items-center gap-2">
          <Input
            type="number"
            min={1}
            max={customMax}
            value={value}
            onChange={(e) => {
              let v = parseInt(e.target.value, 10) || 1;
              if (customMax != null && v > customMax) v = customMax;
              onChange(v);
            }}
            className="w-24"
          />
          <span className="text-sm text-muted-foreground">{unit}</span>
        </div>
      )}
    </div>
  );
}
