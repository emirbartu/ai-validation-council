"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { History, ArrowRight, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { getHistory } from "@/lib/api";
import type { AnalysisSummary } from "@/lib/api";

function TimestampCell({ timestamp }: { timestamp: string | null }) {
  const [formatted, setFormatted] = useState("");

  useEffect(() => {
    if (timestamp) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFormatted(new Date(timestamp).toLocaleDateString());
    }
  }, [timestamp]);

  return <>{timestamp ? formatted : "-"}</>;
}

export default function HistoryPage() {
  const { push } = useRouter();
  const [data, setData] = useState<{
    analyses: AnalysisSummary[];
    loading: boolean;
    error: string | null;
  }>({ analyses: [], loading: true, error: null });

  useEffect(() => {
    getHistory(50)
      .then((result) => setData({ analyses: result.analyses, loading: false, error: null }))
      .catch((err) =>
        setData({ analyses: [], loading: false, error: err instanceof Error ? err.message : "Failed to load history" })
      );
  }, []);

  const { analyses, loading, error } = data;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <History className="size-6 text-muted-foreground" />
          <h1 className="text-2xl font-semibold tracking-tight">Analysis History</h1>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : analyses.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <History className="size-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                No analyses yet. Run your first analysis.
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Past Analyses{" "}
                <Badge variant="secondary" className="ml-2">
                  {analyses.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Query</TableHead>
                    <TableHead className="text-right">Confidence</TableHead>
                    <TableHead className="text-right">Divergences</TableHead>
                    <TableHead className="w-16"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analyses.map((a) => (
                    <TableRow
                      key={a.analysis_id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => push(`/analysis/${a.analysis_id}`)}
                    >
                      <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                        <TimestampCell timestamp={a.timestamp} />
                      </TableCell>
                      <TableCell className="text-sm font-medium max-w-md truncate">
                        {a.query}
                      </TableCell>
                      <TableCell className="text-right">
                        <span
                          className={
                            a.confidence >= 60
                              ? "text-emerald-400"
                              : a.confidence >= 40
                              ? "text-amber-400"
                              : "text-rose-400"
                          }
                        >
                          {a.confidence.toFixed(0)}
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-sm text-muted-foreground">
                        {a.divergence_count}
                      </TableCell>
                      <TableCell>
                        <ArrowRight className="size-4 text-muted-foreground" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
