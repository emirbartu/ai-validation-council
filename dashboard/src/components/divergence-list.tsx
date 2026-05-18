"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { GitCompare } from "lucide-react";
import type { DivergencePoint } from "@/lib/api";

interface DivergenceListProps {
  points: DivergencePoint[];
}

export function DivergenceList({ points }: DivergenceListProps) {
  if (!points || points.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <GitCompare className="size-4" />
            Divergence Points
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No disagreements found between council members.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <GitCompare className="size-4" />
          Divergence Points
          <Badge variant="secondary" className="ml-1">
            {points.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {points.map((point, idx) => (
          <div key={point.topic}>
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-foreground">
                {point.topic}
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 p-3">
                  <div className="text-xs font-medium text-emerald-400 mb-1">
                    Position A
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {typeof point.position_a === "string"
                      ? point.position_a
                      : JSON.stringify(point.position_a)}
                  </div>
                </div>
                <div className="rounded-md border border-rose-500/20 bg-rose-500/5 p-3">
                  <div className="text-xs font-medium text-rose-400 mb-1">
                    Position B
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {typeof point.position_b === "string"
                      ? point.position_b
                      : JSON.stringify(point.position_b)}
                  </div>
                </div>
              </div>
              {point.resolution_test && (
                <div className="text-xs text-muted-foreground bg-muted/50 rounded-md p-2">
                  <span className="font-medium">Resolution test:</span>{" "}
                  {point.resolution_test}
                </div>
              )}
            </div>
            {idx < points.length - 1 && <Separator className="mt-4" />}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
