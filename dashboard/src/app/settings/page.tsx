"use client";

import { useState, useEffect } from "react";
import {
  Settings,
  TrendingUp,
  ShieldAlert,
  GitCompare,
  Eye,
  EyeOff,
  Zap,
  Save,
  MessageSquare,
  Newspaper,
  Globe,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getSettings, updateSettings, testModelConnection } from "@/lib/api";
import type { AppSettings } from "@/lib/api";

function Switch({
  checked,
  onCheckedChange,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-emerald-500" : "bg-muted"
      )}
    >
      <span
        className={cn(
          "pointer-events-none block size-4 rounded-full bg-background shadow-lg ring-0 transition duration-200 ease-in-out",
          checked ? "translate-x-4" : "translate-x-0"
        )}
      />
    </button>
  );
}

function Tabs({
  value,
  onValueChange,
  tabs,
}: {
  value: string;
  onValueChange: (v: string) => void;
  tabs: { value: string; label: string }[];
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-border/40 bg-card p-1">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onValueChange(tab.value)}
          className={cn(
            "rounded-md px-4 py-2 text-sm font-medium transition-all",
            value === tab.value
              ? "bg-muted text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

const PROVIDER_OPTIONS = [
  { value: "", label: "Default (uses global LLM key)" },
  { value: "custom", label: "Custom (OpenAI-compatible)" },
];

function getPlaceholderUrl(_provider: string): string {
  return "";
}

function AgentCard({
  title,
  badge,
  badgeClass,
  icon: Icon,
  model,
  baseUrl,
  apiKey,
  prefix,
  initialProvider,
  onProviderChange,
}: {
  title: string;
  badge: string;
  badgeClass: string;
  icon: React.ComponentType<{ className?: string }>;
  model: string;
  baseUrl: string | null;
  apiKey: string | null;
  prefix: string;
  initialProvider: string;
  onProviderChange: (v: string) => void;
}) {
  const [m, setM] = useState(model || "");
  const [url, setUrl] = useState(baseUrl || "");
  const [key, setKey] = useState(apiKey && apiKey !== "**********" ? apiKey : "");
  const [provider, setProvider] = useState(initialProvider || "");
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const testUrl = url || getPlaceholderUrl(provider);
      const result = await testModelConnection(
        m,
        testUrl,
        key || undefined
      );
      setTestResult({
        success: result.success,
        message: result.success
          ? result.response || "Connection successful"
          : result.error || "Connection failed",
      });
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : "Test failed",
      });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setTestResult(null);
    try {
      await updateSettings({
        [`${prefix}_model`]: m,
        [`${prefix}_base_url`]: url || null,
        [`${prefix}_api_key`]: key || null,
        [`${prefix}_provider`]: provider,
      } as Partial<AppSettings>);
      onProviderChange(provider);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : "Save failed",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-muted">
            <Icon className="size-5 text-muted-foreground" />
          </div>
          <div className="space-y-0.5">
            <CardTitle className="text-base">{title}</CardTitle>
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                badgeClass
              )}
            >
              {badge}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Model</label>
          <Input
            onChange={(e) => setM(e.target.value)}
            placeholder="e.g. gpt-4o-mini"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Base URL</label>
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={getPlaceholderUrl(provider)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">API Key</label>
          <div className="relative">
            <Input
              type={showKey ? "text" : "password"}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder={key ? "••••••••" : "Leave empty to keep current key"}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {showKey ? (
                <EyeOff className="size-4" />
              ) : (
                <Eye className="size-4" />
              )}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Provider</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 text-foreground"
          >
            {PROVIDER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        {testResult && (
          <div
            className={cn(
              "flex items-center gap-2 rounded-md border px-3 py-2 text-sm",
              testResult.success
                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                : "border-rose-500/20 bg-rose-500/10 text-rose-400"
            )}
          >
            {testResult.success ? (
              <CheckCircle2 className="size-4 shrink-0" />
            ) : (
              <XCircle className="size-4 shrink-0" />
            )}
            {testResult.message}
          </div>
        )}
        <div className="flex items-center gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={testing || !m.trim()}
          >
            {testing ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Zap className="size-4" />
            )}
            Test Connection
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Save className="size-4" />
            )}
            {saved ? "Saved!" : "Save"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function DataProviderCard({
  name,
  icon: Icon,
  iconColor,
  enabled,
  description,
  statusText,
  onToggle,
}: {
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  enabled: boolean;
  description: string;
  statusText: string;
  onToggle: (v: boolean) => void;
}) {
  const [updating, setUpdating] = useState(false);

  async function handleToggle(v: boolean) {
    setUpdating(true);
    try {
      await updateSettings({
        [`enable_${name.toLowerCase()}`]: v,
      } as Partial<AppSettings>);
      onToggle(v);
    } catch {
    } finally {
      setUpdating(false);
    }
  }

  return (
    <Card className="transition-colors hover:bg-muted/30">
      <CardContent className="p-0">
        <div className="flex items-start gap-4 p-4">
          <div
            className={cn(
              "flex size-10 shrink-0 items-center justify-center rounded-lg",
              iconColor
            )}
          >
            <Icon className="size-5 text-white" />
          </div>
          <div className="flex-1 space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">{name}</div>
                <div className="text-xs text-muted-foreground">
                  {statusText}
                </div>
              </div>
              <Switch
                checked={enabled}
                onCheckedChange={handleToggle}
                disabled={updating}
              />
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {description}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("models");

  useEffect(() => {
    getSettings()
      .then((data) => setSettings(data.settings))
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : "Failed to load settings"
        )
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <Skeleton className="size-7 rounded-lg" />
            <Skeleton className="h-8 w-32" />
          </div>
          <Skeleton className="h-10 w-64" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Skeleton className="h-[28rem]" />
            <Skeleton className="h-[28rem]" />
            <Skeleton className="h-[28rem]" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !settings) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="flex items-center gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4 shrink-0" />
          {error || "Failed to load settings"}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Settings className="size-7 text-muted-foreground" />
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        </div>

        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          tabs={[
            { value: "models", label: "Models & Providers" },
            { value: "data", label: "Data Providers" },
          ]}
        />

        {activeTab === "models" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <AgentCard
              title="Market Analyst"
              badge="Analyst"
              badgeClass="bg-analyst/15 text-analyst"
              icon={TrendingUp}
              model={settings.market_analyst_model}
              baseUrl={settings.market_analyst_base_url}
              apiKey={settings.market_analyst_api_key}
              prefix="market_analyst"
              initialProvider={settings.market_analyst_provider}
              onProviderChange={(v) => setSettings(s => s ? {...s, market_analyst_provider: v} : s)}
            />
            <AgentCard
              title="Devil's Advocate"
              badge="Advocate"
              badgeClass="bg-advocate/15 text-advocate"
              icon={ShieldAlert}
              model={settings.devils_advocate_model}
              baseUrl={settings.devils_advocate_base_url}
              apiKey={settings.devils_advocate_api_key}
              prefix="devils_advocate"
              initialProvider={settings.devils_advocate_provider}
              onProviderChange={(v) => setSettings(s => s ? {...s, devils_advocate_provider: v} : s)}
            />
            <AgentCard
              title="Divergence Detector"
              badge="Divergence"
              badgeClass="bg-confidence/15 text-confidence"
              icon={GitCompare}
              model={settings.divergence_model}
              baseUrl={settings.divergence_base_url}
              apiKey={settings.divergence_api_key}
              prefix="divergence"
              initialProvider={settings.divergence_provider}
              onProviderChange={(v) => setSettings(s => s ? {...s, divergence_provider: v} : s)}
            />
          </div>
        )}

        {activeTab === "data" && (
          <div className="grid grid-cols-1 gap-4 max-w-2xl">
            <DataProviderCard
              name="Reddit"
              icon={MessageSquare}
              iconColor="bg-rose-500"
              enabled={settings.enable_reddit}
              description="Collects real-time posts and discussions from Reddit using Serper API. Provides demographic sentiment and market demand signals."
              statusText={
                settings.enable_reddit
                  ? "Enabled — using Serper API"
                  : "Disabled"
              }
              onToggle={(v) =>
                setSettings((s) => (s ? { ...s, enable_reddit: v } : s))
              }
            />
            <DataProviderCard
              name="HackerNews"
              icon={Newspaper}
              iconColor="bg-amber-500"
              enabled={settings.enable_hackernews}
              description="Fetches stories and comments from Hacker News via Algolia API. Strong signal for developer tools and B2B SaaS ideas."
              statusText={
                settings.enable_hackernews
                  ? "Enabled — using Algolia API"
                  : "Disabled"
              }
              onToggle={(v) =>
                setSettings((s) => (s ? { ...s, enable_hackernews: v } : s))
              }
            />
            <DataProviderCard
              name="Crawl4AI"
              icon={Globe}
              iconColor="bg-blue-500"
              enabled={settings.enable_crawl4ai}
              description="Deep web crawling for competitor landing pages, pricing pages, and feature matrices. Provides structured competitive intelligence."
              statusText={settings.enable_crawl4ai ? "Enabled" : "Disabled"}
              onToggle={(v) =>
                setSettings((s) => (s ? { ...s, enable_crawl4ai: v } : s))
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
