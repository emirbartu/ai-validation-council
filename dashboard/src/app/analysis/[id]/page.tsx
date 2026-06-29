"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  FileText,
  Lightbulb,
  AlertTriangle,
  Zap,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { AnalysisPanel } from "@/components/analysis-panel";
import { ConfidenceGauge } from "@/components/confidence-gauge";
import { DivergenceList } from "@/components/divergence-list";
import { getAnalysis } from "@/lib/api";
import type { AnalysisDetail, AgentOutput, KillShot } from "@/lib/api";
import { cn } from "@/lib/utils";

function TimestampDisplay({ timestamp }: { timestamp: string }) {
  const [formatted, setFormatted] = useState("");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFormatted(
      new Date(timestamp).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    );
  }, [timestamp]);

  return <span>{formatted}</span>;
}

function isAgentOutput(obj: unknown): obj is AgentOutput {
  return (
    typeof obj === "object" &&
    obj !== null &&
    "role" in obj &&
    typeof (obj as AgentOutput).role === "string"
  );
}

function extractKillShotsFromContent(content: string): KillShot[] {
  const killShots: KillShot[] = [];
  const regex =
    /(?:^|\n)\s*(?:#+\s*)?Kill\s+Shot\s+(\d+)[\.:\s\-]+([^\n]+)(?:\n+([\s\S]*?))?(?=\n\s*(?:#+\s*)?Kill\s+Shot\s+\d+|\n\s*(?:###?\s*)?(?:One-Sentence\s+)?Verdict|\n\s*(?:The\s+Fatal|Named\s+Competitor|Data\s+Limitation|$))/gi;

  let match;
  while ((match = regex.exec(content)) !== null) {
    killShots.push({
      number: match[1],
      title: match[2].trim(),
      details: (match[3] || "").trim().slice(0, 1500),
    });
  }

  if (killShots.length === 0) {
    const simpleRegex = /Kill\s+Shot\s+(\d+)[\.:\s\-]+([^\n]+)/gi;
    while ((match = simpleRegex.exec(content)) !== null) {
      killShots.push({
        number: match[1],
        title: match[2].trim(),
        details: "",
      });
    }
  }

  return killShots;
}

function parseAgentOutput(
  raw: AgentOutput | Record<string, unknown> | string
): { content: string; killShots?: KillShot[]; verdict?: string } {
  if (typeof raw === "string") {
    return { content: raw };
  }

  if (isAgentOutput(raw)) {
    const killShots =
      raw.kill_shots && raw.kill_shots.length > 0
        ? raw.kill_shots
        : extractKillShotsFromContent(raw.content);
    return {
      content: raw.content,
      killShots: killShots.length > 0 ? killShots : undefined,
      verdict: raw.verdict,
    };
  }

  const content =
    typeof raw.content === "string"
      ? raw.content
      : JSON.stringify(raw, null, 2);
  const killShots = extractKillShotsFromContent(content);
  return {
    content,
    killShots: killShots.length > 0 ? killShots : undefined,
  };
}

function Tabs({ active, onChange, tabs }: { active: string; onChange: (v: string) => void; tabs: { id: string; label: string }[] }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-border/40 bg-card p-1">
      {tabs.map((tab) => (
        <button key={tab.id} onClick={() => onChange(tab.id)}
          className={cn("rounded-md px-4 py-2 text-sm font-medium transition-all",
            active === tab.id ? "bg-muted text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default function AnalysisDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [data, setData] = useState<{
    analysis: AnalysisDetail | null;
    loading: boolean;
    error: string | null;
  }>({ analysis: null, loading: true, error: null });

  const [activeTab, setActiveTab] = useState("agents");

  useEffect(() => {
    if (!id) return;

    getAnalysis(decodeURIComponent(id))
      .then((result) => setData({ analysis: result, loading: false, error: null }))
      .catch((err) =>
        setData({ analysis: null, loading: false, error: err instanceof Error ? err.message : "Not found" })
      );
  }, [id]);

  const { analysis, loading, error } = data;

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 space-y-6">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-4 w-64" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="size-8 text-destructive mx-auto mb-3" />
            <h2 className="text-lg font-semibold mb-1">Analysis not found</h2>
            <p className="text-sm text-muted-foreground">
              {error || "The requested analysis could not be loaded."}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const ma = parseAgentOutput(analysis.market_analyst);
  const da = parseAgentOutput(analysis.devils_advocate);

  const divergencePoints: Array<{
    topic: string;
    position_a: Record<string, unknown>;
    position_b: Record<string, unknown>;
    resolution_test: string;
  }> = [];

  if (
    typeof analysis.market_analyst === "object" &&
    analysis.market_analyst !== null &&
    "divergence_points" in analysis.market_analyst
  ) {
    const dp = (analysis.market_analyst as Record<string, unknown>)
      .divergence_points;
    if (Array.isArray(dp)) {
      divergencePoints.push(...dp);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 space-y-6">
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <FileText className="size-5 text-muted-foreground" />
          <h1 className="text-2xl font-semibold tracking-tight line-clamp-2">
            {analysis.query}
          </h1>
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          {analysis.timestamp && <TimestampDisplay timestamp={analysis.timestamp} />}
          <Badge variant="outline" className="font-mono text-xs">
            {analysis.analysis_id}
          </Badge>
        </div>
      </div>

      <Tabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "agents", label: "Agents" },
          { id: "summary", label: "Summary" },
        ]}
      />

      {activeTab === "agents" && (
        <>
          <Card>
            <CardContent className="py-6">
              <ConfidenceGauge score={analysis.confidence} />
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <AnalysisPanel
              role="market_analyst"
              content={ma.content}
              variant="analyst"
            />
            <AnalysisPanel
              role="devils_advocate"
              content={da.content}
              killShots={da.killShots}
              verdict={da.verdict}
              variant="advocate"
            />
          </div>

          {divergencePoints.length > 0 && (
            <DivergenceList points={divergencePoints} />
          )}

          {analysis.divergence_count > 0 && divergencePoints.length === 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Divergence Points</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {analysis.divergence_count} disagreement
                  {analysis.divergence_count === 1 ? "" : "s"} detected between
                  council members. Detailed breakdown unavailable in history view.
                </p>
              </CardContent>
            </Card>
          )}

          <Separator />

          <div className="text-xs text-muted-foreground">
            Raw confidence: {analysis.confidence.toFixed(2)} | Divergencies:{" "}
            {analysis.divergence_count}
          </div>
        </>
      )}

      {activeTab === "summary" && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Debate Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {analysis.debate_summary ? (
                <>
                  <div>
                    <h4 className="text-sm font-semibold mb-2">What the council agreed on</h4>
                    <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
                      {analysis.debate_summary.what_agents_agreed_on.map((item, i) => (
                        <li key={`agree-${i}`}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                      <Lightbulb className="size-4 text-yellow-400" />
                      What would strengthen this idea
                    </h4>
                    <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
                      {analysis.debate_summary.what_would_strengthen_the_idea.map((item, i) => (
                        <li key={`strength-${i}`}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                      <AlertTriangle className="size-4 text-orange-400" />
                      Key disadvantages
                    </h4>
                    <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
                      {analysis.debate_summary.key_disadvantages.map((item, i) => (
                        <li key={`disadv-${i}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No debate summary available.</p>
              )}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl border bg-emerald-500/10 border-emerald-500/20 p-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400 mb-3 flex items-center gap-2">
                <TrendingUp className="size-4" />
                Strengths
              </h4>
              {analysis.swot && analysis.swot.strengths.length > 0 ? (
                <ul className="list-disc pl-4 space-y-1 text-sm text-muted-foreground">
                  {analysis.swot.strengths.map((item, i) => (
                    <li key={`s-${i}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No strengths data.</p>
              )}
            </div>

            <div className="rounded-xl border bg-rose-500/10 border-rose-500/20 p-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-rose-400 mb-3 flex items-center gap-2">
                <TrendingDown className="size-4" />
                Weaknesses
              </h4>
              {analysis.swot && analysis.swot.weaknesses.length > 0 ? (
                <ul className="list-disc pl-4 space-y-1 text-sm text-muted-foreground">
                  {analysis.swot.weaknesses.map((item, i) => (
                    <li key={`w-${i}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No weaknesses data.</p>
              )}
            </div>

            <div className="rounded-xl border bg-blue-500/10 border-blue-500/20 p-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-blue-400 mb-3 flex items-center gap-2">
                <Zap className="size-4" />
                Opportunities
              </h4>
              {analysis.swot && analysis.swot.opportunities.length > 0 ? (
                <ul className="list-disc pl-4 space-y-1 text-sm text-muted-foreground">
                  {analysis.swot.opportunities.map((item, i) => (
                    <li key={`o-${i}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No opportunities data.</p>
              )}
            </div>

            <div className="rounded-xl border bg-amber-500/10 border-amber-500/20 p-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400 mb-3 flex items-center gap-2">
                <AlertTriangle className="size-4" />
                Threats
              </h4>
              {analysis.swot && analysis.swot.threats.length > 0 ? (
                <ul className="list-disc pl-4 space-y-1 text-sm text-muted-foreground">
                  {analysis.swot.threats.map((item, i) => (
                    <li key={`t-${i}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No threats data.</p>
              )}
            </div>
          </div>

          {analysis.addendum && (
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-xs",
                      analysis.addendum.raised_by.toLowerCase().includes("advocate") ||
                        analysis.addendum.raised_by.toLowerCase().includes("devil")
                        ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                        : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                    )}
                  >
                    {analysis.addendum.raised_by}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    Additional Insight
                  </span>
                </div>
                <CardTitle className="text-base mt-2">{analysis.addendum.topic}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {analysis.addendum.insight}
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
