import { useEffect, useMemo, useState } from "react";

import { getAiStats, getOpenRouterMetrics } from "../api/ai";
import { getClients } from "../api/clients";
import SkeletonCard from "../components/SkeletonCard";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { RU } from "../i18n/ru";

const OPENROUTER_ACCESS_ERROR =
  "\u041d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a OpenRouter \u043c\u0435\u0442\u0440\u0438\u043a\u0430\u043c (\u043d\u0443\u0436\u0435\u043d management key).";
const OPENROUTER_UNAVAILABLE_ERROR =
  "OpenRouter \u043c\u0435\u0442\u0440\u0438\u043a\u0438 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b.";

function safeNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function formatCompact(value) {
  const n = safeNumber(value);
  if (n === null) return "\u2014";
  if (Math.abs(n) >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

function formatSpendUsd(value) {
  const n = safeNumber(value);
  if (n === null) return "\u2014";
  return `$${n.toFixed(2)}`;
}

function extractCreditsBalance(creditsPayload) {
  if (!creditsPayload || typeof creditsPayload !== "object") return null;
  const source =
    creditsPayload && typeof creditsPayload.data === "object"
      ? creditsPayload.data
      : creditsPayload;

  const directCandidates = [
    "balance",
    "credits",
    "remaining",
    "remaining_credits",
    "available_credits",
    "credit_balance",
    "usd_balance",
  ];
  for (const key of directCandidates) {
    const value = safeNumber(source?.[key]);
    if (value !== null) return value;
  }

  const totalCredits = safeNumber(source?.total_credits);
  const totalUsage = safeNumber(source?.total_usage);
  if (totalCredits !== null && totalUsage !== null) {
    return totalCredits - totalUsage;
  }

  if (totalCredits !== null) return totalCredits;
  return null;
}

function normalizeOpenRouterError(rawError) {
  const text = String(rawError || "").toLowerCase();
  if (!text) return "";
  if (text.includes("management key") || text.includes("401") || text.includes("403")) {
    return OPENROUTER_ACCESS_ERROR;
  }
  return OPENROUTER_UNAVAILABLE_ERROR;
}

export default function BotPage() {
  const [stats, setStats] = useState(null);
  const [clients, setClients] = useState([]);
  const [openrouterData, setOpenrouterData] = useState(null);
  const [openrouterLoading, setOpenrouterLoading] = useState(true);
  const [openrouterError, setOpenrouterError] = useState("");

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const [ai, clientData] = await Promise.all([getAiStats(), getClients()]);
        if (!cancelled) {
          setStats(ai);
          setClients(clientData.items ?? clientData);
        }
      } catch (_error) {
        if (!cancelled) {
          setStats({ totalResponses: 0, activeUsers: 0 });
          setClients([]);
        }
      }

      try {
        const metrics = await getOpenRouterMetrics();
        if (!cancelled) {
          setOpenrouterData(metrics);
          setOpenrouterError(normalizeOpenRouterError(metrics?.error));
        }
      } catch (_error) {
        if (!cancelled) {
          setOpenrouterData(null);
          setOpenrouterError(OPENROUTER_UNAVAILABLE_ERROR);
        }
      } finally {
        if (!cancelled) {
          setOpenrouterLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const activity = openrouterData?.activity || null;
  const spendUsd = activity?.spend_usd ?? null;
  const requests = activity?.requests ?? null;
  const tokens = activity?.tokens ?? null;
  const creditsBalance = useMemo(
    () => extractCreditsBalance(openrouterData?.credits),
    [openrouterData],
  );

  if (!stats) {
    return <SkeletonCard rows={4} className="p-6" />;
  }

  const activeUsers = clients
    .filter((c) => c.lastActivity)
    .sort((a, b) => (a.lastActivity < b.lastActivity ? 1 : -1))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">OpenRouter (30 \u0434\u043d\u0435\u0439)</h3>
        </CardHeader>
        <CardContent className="space-y-4">
          {openrouterError && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-700">
              {openrouterError}
            </div>
          )}
          {openrouterLoading ? (
            <SkeletonCard rows={2} className="p-4" />
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Spend USD</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900">
                    {formatSpendUsd(spendUsd)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Requests</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900">
                    {formatCompact(requests)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Tokens</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900">
                    {formatCompact(tokens)}
                  </p>
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Credits</p>
                <p className="mt-2 text-3xl font-semibold text-slate-900">
                  {creditsBalance === null ? "\u2014" : formatSpendUsd(creditsBalance)}
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">{RU.labels.botPageTitle}</h2>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm text-slate-500">{RU.labels.responses}</p>
              <p className="text-2xl font-semibold text-slate-900">{stats.totalResponses}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm text-slate-500">{RU.labels.activeUsers}</p>
              <p className="text-2xl font-semibold text-slate-900">{stats.activeUsers}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">{RU.labels.recentBotActivity}</h3>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {activeUsers.map((client) => (
              <div key={client.id} className="flex justify-between text-sm">
                <span className="text-slate-700">{client.name}</span>
                <span className="text-slate-500">{client.lastActivity}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
