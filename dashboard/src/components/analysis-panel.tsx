"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Target } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { KillShot } from "@/lib/api";

interface AnalysisPanelProps {
  role: string;
  content: string;
  killShots?: KillShot[];
  verdict?: string;
  variant: "analyst" | "advocate";
}

export function AnalysisPanel({
  role,
  content,
  killShots,
  verdict,
  variant,
}: AnalysisPanelProps) {
  const [isOpen, setIsOpen] = useState(true);

  const isAnalyst = variant === "analyst";
  const accentColor = isAnalyst ? "border-l-emerald-500" : "border-l-rose-500";
  const badgeVariant = isAnalyst ? "secondary" : "destructive";
  const badgeText = isAnalyst ? "Market Analyst" : "Devil's Advocate";

  return (
    <Card className={cn("border-l-4", accentColor)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge variant={badgeVariant}>{badgeText}</Badge>
            {verdict && (
              <span className="text-sm text-muted-foreground truncate max-w-md">
                {verdict}
              </span>
            )}
          </div>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="p-1 hover:bg-muted rounded-md transition-colors"
            aria-label={isOpen ? "Collapse" : "Expand"}
          >
            {isOpen ? (
              <ChevronUp className="size-4" />
            ) : (
              <ChevronDown className="size-4" />
            )}
          </button>
        </div>
      </CardHeader>
      {isOpen && (
        <CardContent className="space-y-4">
          {killShots && killShots.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-rose-400">
                <Target className="size-4" />
                <span>Kill Shots</span>
              </div>
              <div className="space-y-2">
                {killShots.map((ks) => (
                  <div
                    key={ks.number}
                    className="rounded-md border border-rose-500/20 bg-rose-500/5 p-3"
                  >
                    <div className="text-sm font-semibold text-rose-300">
                      {ks.number}. {ks.title}
                    </div>
                    {ks.details && (
                      <div className="mt-1 text-sm text-muted-foreground leading-relaxed">
                        {ks.details}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="text-sm leading-relaxed whitespace-pre-wrap text-foreground/90">
            {content}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
