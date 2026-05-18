"use client";

import { cn } from "@/lib/utils";

interface ConfidenceGaugeProps {
  score: number;
}

function getConfidenceColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-amber-500";
  if (score >= 40) return "bg-orange-500";
  if (score >= 20) return "bg-rose-500";
  return "bg-slate-500";
}

function getConfidenceLabel(score: number): string {
  if (score >= 80) return "High confidence — strong data, minimal disagreement";
  if (score >= 60) return "Moderate confidence — reasonable data, some divergent views";
  if (score >= 40) return "Low confidence — limited data or significant disagreement";
  if (score >= 20) return "Very low confidence — insufficient data or major disagreements";
  return "Unreliable — critical data or consensus gaps";
}

function getConfidenceTextColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-amber-400";
  if (score >= 40) return "text-orange-400";
  if (score >= 20) return "text-rose-400";
  return "text-slate-400";
}

export function ConfidenceGauge({ score }: ConfidenceGaugeProps) {
  const clampedScore = Math.max(0, Math.min(100, score));
  const colorClass = getConfidenceColor(clampedScore);
  const label = getConfidenceLabel(clampedScore);
  const textColor = getConfidenceTextColor(clampedScore);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">
          Confidence Score
        </span>
        <span className={cn("text-2xl font-bold", textColor)}>
          {clampedScore}
          <span className="text-sm font-normal text-muted-foreground">/100</span>
        </span>
      </div>
      <div className="h-3 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", colorClass)}
          style={{ width: `${clampedScore}%` }}
        />
      </div>
      <p className="text-sm text-muted-foreground leading-relaxed">{label}</p>
    </div>
  );
}
