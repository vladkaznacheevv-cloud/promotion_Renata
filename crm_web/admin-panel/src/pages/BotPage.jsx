import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getAiStats, getOpenRouterMetrics } from "../api/ai";
import { getClients } from "../api/clients";
import SkeletonCard from "../components/SkeletonCard";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { RU } from "../i18n/ru";

const OPENROUTER_ACCESS_ERROR =
  "Нет доступа к OpenRouter метрикам (нужен management key).";
const OPENROUTER_UNAVAILABLE_ERROR = "OpenRouter метрики временно недоступны.";
const NO_DATA_TEXT = "Нет данных за период";
const OTHER_MODEL_LABEL = "Other";
const MODEL_COLORS = [
  "#2563eb",
  "#16a34a",
  "#9333ea",
  "#ea580c",
  "#0891b2",
  "#dc2626",
  "#475569",
];

const METRIC_CONFIG = {
  spend: {
    title: "Запросы по дням",
    kpiLabel: "Запросы",
    rowKey: "usage",
    sumFormatter: (value) => `$${Number(value || 0).toFixed(3)}`,
    tooltipFormatter: (value) => `$${Number(value || 0).toFixed(3)}`,
  },
  requests: {
    title: "Ответы по дням",
    kpiLabel: "Ответы",
    rowKey: "requests",
    sumFormatter: (value) => formatInteger(value),
    tooltipFormatter: (value) => formatInteger(value),
  },
  tokens: {
    title: "Токены по дням",
    kpiLabel: "Токены",
    rowKey: "tokens",
    sumFormatter: (value) => formatInteger(value),
    tooltipFormatter: (value) => formatInteger(value),
  },
};

function safeNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function formatCompact(value) {
  const n = safeNumber(value);
  if (Math.abs(n) >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

function formatInteger(value) {
  return Math.round(safeNumber(value)).toLocaleString("ru-RU");
}

function formatSpendUsd(value) {
  return `$${safeNumber(value).toFixed(2)}`;
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
    const value = source?.[key];
    if (value !== undefined && value !== null && value !== "") {
      return safeNumber(value);
    }
  }

  const totalCredits = source?.total_credits;
  const totalUsage = source?.total_usage;
  if (totalCredits !== undefined && totalUsage !== undefined) {
    return safeNumber(totalCredits) - safeNumber(totalUsage);
  }
  if (totalCredits !== undefined) return safeNumber(totalCredits);
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

function getLast30UtcDays() {
  const days = [];
  const now = new Date();
  for (let i = 29; i >= 0; i -= 1) {
    const day = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - i),
    );
    days.push(day.toISOString().slice(0, 10));
  }
  return days;
}

function formatDayLabel(day) {
  if (!day || day.length < 10) return day;
  return `${day.slice(8, 10)}.${day.slice(5, 7)}`;
}

function normalizeRows(rawRows, daySet) {
  const rows = Array.isArray(rawRows) ? rawRows : [];
  return rows
    .map((row) => ({
      date: String(row?.date || "").slice(0, 10),
      model: String(row?.model || "").trim() || "unknown",
      usage: safeNumber(row?.usage),
      requests: Math.round(safeNumber(row?.requests)),
      tokens: Math.round(safeNumber(row?.tokens)),
    }))
    .filter((row) => daySet.has(row.date));
}

function buildMetricView(rows, days, metricKey, topN = 6) {
  const rowField = METRIC_CONFIG[metricKey].rowKey;
  const totalsByModel = new Map();
  for (const row of rows) {
    const value = safeNumber(row[rowField]);
    totalsByModel.set(row.model, (totalsByModel.get(row.model) || 0) + value);
  }

  const sortedModels = [...totalsByModel.entries()]
    .sort((a, b) => b[1] - a[1])
    .filter((entry) => entry[1] > 0);
  const topModelEntries = sortedModels.slice(0, topN);
  const topModelSet = new Set(topModelEntries.map((entry) => entry[0]));
  const otherTotal = sortedModels.slice(topN).reduce((sum, entry) => sum + entry[1], 0);

  const modelKeys = topModelEntries.map((entry) => entry[0]);
  if (otherTotal > 0) modelKeys.push(OTHER_MODEL_LABEL);

  const dataByDay = new Map(days.map((date) => [date, { date, dayLabel: formatDayLabel(date) }]));
  for (const day of days) {
    const dayRow = dataByDay.get(day);
    for (const modelKey of modelKeys) {
      dayRow[modelKey] = 0;
    }
  }

  for (const row of rows) {
    const dayRow = dataByDay.get(row.date);
    if (!dayRow) continue;
    const value = safeNumber(row[rowField]);
    const modelKey = topModelSet.has(row.model) ? row.model : OTHER_MODEL_LABEL;
    if (!modelKeys.includes(modelKey)) continue;
    dayRow[modelKey] = safeNumber(dayRow[modelKey]) + value;
  }

  const tableRows = topModelEntries.map(([model, sum]) => ({ model, sum }));
  if (otherTotal > 0) tableRows.push({ model: OTHER_MODEL_LABEL, sum: otherTotal });
  if (tableRows.length === 1 && tableRows[0].model !== OTHER_MODEL_LABEL) {
    tableRows.push({ model: OTHER_MODEL_LABEL, sum: 0 });
  }
  tableRows.sort((a, b) => b.sum - a.sum);

  return {
    data: days.map((day) => dataByDay.get(day)),
    modelKeys,
    tableRows,
    hasData: rows.length > 0,
  };
}

function MetricChartBlock({ title, metricKey, view }) {
  const config = METRIC_CONFIG[metricKey];
  const colorMap = useMemo(() => {
    const pairs = view.modelKeys.map((model, index) => [
      model,
      MODEL_COLORS[index % MODEL_COLORS.length],
    ]);
    return new Map(pairs);
  }, [view.modelKeys]);

  if (!view.hasData) {
    return (
      <Card>
        <CardHeader>
          <h4 className="text-base font-semibold text-slate-900">{title}</h4>
        </CardHeader>
        <CardContent>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            {NO_DATA_TEXT}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h4 className="text-base font-semibold text-slate-900">{title}</h4>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={view.data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="dayLabel" tick={{ fontSize: 12 }} interval={2} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value) => config.tooltipFormatter(value)}
                labelFormatter={(label, payload) => {
                  if (payload && payload[0] && payload[0].payload) {
                    return payload[0].payload.date;
                  }
                  return label;
                }}
              />
              <Legend />
              {view.modelKeys.map((model) => (
                <Bar
                  key={model}
                  dataKey={model}
                  stackId="metric"
                  fill={colorMap.get(model)}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div>
          <h5 className="mb-2 text-sm font-medium text-slate-700">Sum по моделям</h5>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-1.5 pr-4 font-medium">Model</th>
                  <th className="py-1.5 font-medium">Sum</th>
                </tr>
              </thead>
              <tbody>
                {view.tableRows.map((row) => (
                  <tr key={`${metricKey}-${row.model}`} className="border-t border-slate-100">
                    <td className="py-2 pr-4 text-slate-700">{row.model}</td>
                    <td className="py-2 text-slate-900">{config.sumFormatter(row.sum)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
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

  const days = useMemo(() => getLast30UtcDays(), []);
  const daySet = useMemo(() => new Set(days), [days]);
  const activityRows = useMemo(
    () => normalizeRows(openrouterData?.activity_rows, daySet),
    [openrouterData, daySet],
  );

  const spendFromRows = useMemo(
    () => activityRows.reduce((sum, row) => sum + safeNumber(row.usage), 0),
    [activityRows],
  );
  const requestsFromRows = useMemo(
    () => activityRows.reduce((sum, row) => sum + safeNumber(row.requests), 0),
    [activityRows],
  );
  const tokensFromRows = useMemo(
    () => activityRows.reduce((sum, row) => sum + safeNumber(row.tokens), 0),
    [activityRows],
  );

  const spendUsd =
    openrouterData?.activity?.spend_usd ?? (activityRows.length ? spendFromRows : 0);
  const requests =
    openrouterData?.activity?.requests ?? (activityRows.length ? requestsFromRows : 0);
  const tokens = openrouterData?.activity?.tokens ?? (activityRows.length ? tokensFromRows : 0);
  const creditsBalance = useMemo(
    () => extractCreditsBalance(openrouterData?.credits),
    [openrouterData],
  );

  const spendView = useMemo(
    () => buildMetricView(activityRows, days, "spend"),
    [activityRows, days],
  );
  const requestsView = useMemo(
    () => buildMetricView(activityRows, days, "requests"),
    [activityRows, days],
  );
  const tokensView = useMemo(
    () => buildMetricView(activityRows, days, "tokens"),
    [activityRows, days],
  );

  if (!stats) {
    return <SkeletonCard rows={4} className="p-6" />;
  }

  const activeUsers = clients
    .filter((c) => c.lastActivity)
    .sort((a, b) => (a.lastActivity < b.lastActivity ? 1 : -1))
    .slice(0, 5);

  const shouldShowNoData =
    !openrouterLoading && !openrouterError && activityRows.length === 0;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">OpenRouter (30 дней)</h3>
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
            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  {METRIC_CONFIG.spend.kpiLabel}
                </p>
                <p className="mt-2 text-3xl font-semibold text-slate-900">
                  {formatSpendUsd(spendUsd)}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  {METRIC_CONFIG.requests.kpiLabel}
                </p>
                <p className="mt-2 text-3xl font-semibold text-slate-900">
                  {formatInteger(requests)}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  {METRIC_CONFIG.tokens.kpiLabel}
                </p>
                <p className="mt-2 text-3xl font-semibold text-slate-900">
                  {formatCompact(tokens)}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Сумма</p>
                <p className="mt-2 text-3xl font-semibold text-slate-900">
                  {creditsBalance === null ? "—" : formatSpendUsd(creditsBalance)}
                </p>
              </div>
            </div>
          )}
          {shouldShowNoData && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">
              {NO_DATA_TEXT}
            </div>
          )}
        </CardContent>
      </Card>

      {!openrouterError && (
        <div className="grid grid-cols-1 gap-6">
          <MetricChartBlock title={METRIC_CONFIG.spend.title} metricKey="spend" view={spendView} />
          <MetricChartBlock
            title={METRIC_CONFIG.requests.title}
            metricKey="requests"
            view={requestsView}
          />
          <MetricChartBlock title={METRIC_CONFIG.tokens.title} metricKey="tokens" view={tokensView} />
        </div>
      )}

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">{RU.labels.botPageTitle}</h2>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm text-slate-500">{RU.labels.aiResponsesAllTime}</p>
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
