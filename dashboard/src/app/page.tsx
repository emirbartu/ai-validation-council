"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, ArrowRight, Clock, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingDots } from "@/components/loading-dots";
import { runAnalysis, getHistory } from "@/lib/api";
import type { AnalysisSummary } from "@/lib/api";

export default function HomePage() {
  const { push } = useRouter();
  const [idea, setIdea] = useState("");
  const [profile, setProfile] = useState("full");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<{
    analyses: AnalysisSummary[];
    loading: boolean;
  }>({ analyses: [], loading: true });

  useEffect(() => {
    getHistory(5)
      .then((data) => setHistory({ analyses: data.analyses, loading: false }))
      .catch(() => setHistory({ analyses: [], loading: false }));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!idea.trim() || loading) return;

    setLoading(true);
    setError(null);

    try {
      const result = await runAnalysis(idea.trim(), profile);
      push(`/analysis/${encodeURIComponent(result.query)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:py-12">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <BrainCircuit className="size-8 text-emerald-400" />
              <h1 className="text-3xl font-semibold tracking-tight">
                AI Validation Council
              </h1>
            </div>
            <p className="text-lg text-muted-foreground leading-relaxed max-w-xl">
              Validate your startup idea through structured adversarial debate.
              Real market data. No sycophancy.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">New Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">
                    Analysis Profile
                  </label>
                  <select
                    value={profile}
                    onChange={(e) => setProfile(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <option value="full">Full Analysis — All agents, complete debate</option>
                    <option value="early_idea">Early Idea — Maximize exploration, 3 rounds</option>
                    <option value="pre_launch">Pre-Launch — Stress test execution risks</option>
                    <option value="pivot">Pivot — Existing product considering change</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label htmlFor="idea" className="text-sm font-medium">
                    Describe your startup idea
                  </label>
                  <Input
                    id="idea"
                    placeholder="An AI meal planner for fitness goals and dietary restrictions…"
                    value={idea}
                    onChange={(e) => setIdea(e.target.value)}
                    disabled={loading}
                    className="h-12"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="size-4" />
                    <span>Analysis takes 3-5 minutes</span>
                  </div>
                  <Button
                    type="submit"
                    disabled={loading || !idea.trim()}
                    className="gap-2"
                  >
                    {loading ? (
                      <>
                        <LoadingDots />
                        Analyzing…
                      </>
                    ) : (
                      <>
                        Analyze
                        <ArrowRight className="size-4" />
                      </>
                    )}
                  </Button>
                </div>
                {error && (
                  <div className="flex items-center gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
                    <AlertCircle className="size-4 shrink-0" />
                    {error}
                  </div>
                )}
              </form>
            </CardContent>
          </Card>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              How it works
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[
                {
                  step: "1",
                  title: "Collect Data",
                  desc: "Reddit + HN scraped in real-time for your query",
                },
                {
                  step: "2",
                  title: "Adversarial Debate",
                  desc: "Market Analyst vs Devil's Advocate with real data",
                },
                {
                  step: "3",
                  title: "Divergence Report",
                  desc: "Where they disagree is where the signal lives",
                },
              ].map((item) => (
                <div
                  key={item.step}
                  className="rounded-lg border border-border/40 bg-card p-4 space-y-2"
                >
                  <div className="text-xs font-mono text-muted-foreground">
                    Step {item.step}
                  </div>
                  <div className="text-sm font-semibold">{item.title}</div>
                  <div className="text-sm text-muted-foreground leading-relaxed">
                    {item.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Recent Analyses
          </h2>
          {history.loading ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : history.analyses.length === 0 ? (
            <Card>
              <CardContent className="py-6 text-center text-sm text-muted-foreground">
                No analyses yet. Run your first analysis.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {history.analyses.map((a) => (
                <button
                  key={a.analysis_id}
                  onClick={() => push(`/analysis/${a.analysis_id}`)}
                  className="w-full text-left rounded-lg border border-border/40 bg-card p-4 hover:bg-muted/50 transition-colors space-y-2"
                >
                  <div className="text-sm font-medium line-clamp-2">
                    {a.query}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span
                      className={
                        a.confidence >= 60
                          ? "text-emerald-400"
                          : a.confidence >= 40
                          ? "text-amber-400"
                          : "text-rose-400"
                      }
                    >
                      {a.confidence.toFixed(0)} confidence
                    </span>
                    <span>{a.divergence_count} divergences</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
