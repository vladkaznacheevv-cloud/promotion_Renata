import { useEffect, useMemo, useState } from "react";
import { DollarSign, TrendingUp, Users, Calendar, Bot } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getAiStats } from "../api/ai";
import { getClients } from "../api/clients";
import { getEvents } from "../api/events";
import { getCatalog } from "../api/catalog";
import { getPayments } from "../api/payments";
import { getRevenueSummary } from "../api/revenue";
import { getGetCourseSummary } from "../api/integrations";
import { DEV_MOCKS, getDevFallbackUsed } from "../api/http";
import { RU, formatCurrencyRub } from "../i18n/ru";
import DashboardStatCard from "../components/DashboardStatCard";
import ErrorBanner from "../components/ErrorBanner";
import SkeletonCard from "../components/SkeletonCard";
import Button from "../components/ui/Button";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Tabs } from "../components/ui/Tabs";

export default function DashboardPage() {
  const [clients, setClients] = useState([]);
  const [events, setEvents] = useState([]);
  const [aiStats, setAiStats] = useState(null);
  const [revenueSummary, setRevenueSummary] = useState(null);
  const [payments, setPayments] = useState([]);
  const [getcourseSummary, setGetcourseSummary] = useState(null);
  const [catalogItems, setCatalogItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [devNotice, setDevNotice] = useState("");
  const [range, setRange] = useState("30d");

  const fetchData = async (withLoading = false) => {
    try {
      if (withLoading) setLoading(true);
      setError("");
      const [clientsRes, eventsRes, aiRes, revenueRes, paymentsRes, gcRes, catalogRes] = await Promise.all([
        getClients(),
        getEvents(),
        getAiStats(),
        getRevenueSummary(),
        getPayments(),
        getGetCourseSummary(),
        getCatalog({ limit: 100 }),
      ]);

      setClients(clientsRes.items ?? clientsRes);
      setEvents(eventsRes.items ?? eventsRes);
      setAiStats(aiRes);
      setRevenueSummary(revenueRes);
      setPayments(paymentsRes.items ?? paymentsRes);
      setGetcourseSummary(gcRes);
      setCatalogItems(catalogRes.items ?? []);

      if (DEV_MOCKS && getDevFallbackUsed()) {
        setDevNotice(RU.messages.backendUnavailableDemo);
      } else {
        setDevNotice("");
      }
    } catch (err) {
      const rawMessage = err?.message || "";
      const message = rawMessage.includes("Failed to fetch")
        ? RU.messages.apiConnectionFailed
        : rawMessage || RU.messages.dataLoadError;

      if (DEV_MOCKS) {
        setDevNotice(RU.messages.backendUnavailableDemo);
      } else {
        setError(message);
      }
    } finally {
      if (withLoading) setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    (async () => {
      if (!active) return;
      await fetchData(true);
    })();
    return () => {
      active = false;
    };
  }, []);

  const stageCounters = useMemo(() => {
    const counters = {
      NEW: 0,
      ENGAGED: 0,
      READY_TO_PAY: 0,
      PAID: 0,
    };
    clients.forEach((client) => {
      const stage = client.stage || "NEW";
      if (Object.hasOwn(counters, stage)) {
        counters[stage] += 1;
      }
    });
    return counters;
  }, [clients]);

  const dashboardStats = useMemo(
    () => [
      {
        title: RU.labels.totalRevenue,
        value: revenueSummary ? formatCurrencyRub(revenueSummary.total || 0) : RU.messages.emDash,
        change: "+15.3%",
        changeType: "positive",
        icon: <DollarSign className="h-6 w-6" />,
      },
      {
        title: RU.labels.activeClients,
        value: clients.length ? clients.length.toLocaleString("ru-RU") : RU.messages.emDash,
        change: "+12.5%",
        changeType: "positive",
        icon: <Users className="h-6 w-6" />,
      },
      {
        title: RU.labels.eventsCount,
        value: events.length ? events.length.toLocaleString("ru-RU") : RU.messages.emDash,
        change: "0%",
        changeType: "neutral",
        icon: <Calendar className="h-6 w-6" />,
      },
      {
        title: RU.labels.aiResponses,
        value: aiStats?.totalResponses ? aiStats.totalResponses.toLocaleString("ru-RU") : RU.messages.emDash,
        change: "+42.3%",
        changeType: "positive",
        icon: <Bot className="h-6 w-6" />,
      },
      {
        title: RU.labels.onlineCourses,
        value: catalogItems.length.toLocaleString("ru-RU"),
        change: "—",
        changeType: "neutral",
        icon: <Calendar className="h-6 w-6" />,
      },
      {
        title: RU.labels.stageNew,
        value: stageCounters.NEW.toLocaleString("ru-RU"),
        change: "—",
        changeType: "neutral",
        icon: <Users className="h-6 w-6" />,
      },
      {
        title: RU.labels.stageEngaged,
        value: stageCounters.ENGAGED.toLocaleString("ru-RU"),
        change: "—",
        changeType: "neutral",
        icon: <TrendingUp className="h-6 w-6" />,
      },
      {
        title: RU.labels.stageReadyToPay,
        value: stageCounters.READY_TO_PAY.toLocaleString("ru-RU"),
        change: "—",
        changeType: "neutral",
        icon: <TrendingUp className="h-6 w-6" />,
      },
      {
        title: RU.labels.stagePaid,
        value: stageCounters.PAID.toLocaleString("ru-RU"),
        change: "—",
        changeType: "positive",
        icon: <TrendingUp className="h-6 w-6" />,
      },
    ],
    [aiStats, clients.length, events.length, revenueSummary, stageCounters, catalogItems.length]
  );

  const paidPayments = useMemo(() => payments.filter((p) => p.status === "paid"), [payments]);

  const revenueSeries = useMemo(() => {
    const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;
    const now = new Date();
    const map = new Map();
    for (let i = days - 1; i >= 0; i -= 1) {
      const day = new Date(now);
      day.setDate(now.getDate() - i);
      const key = day.toISOString().slice(0, 10);
      map.set(key, 0);
    }
    paidPayments.forEach((payment) => {
      const key = String(payment.created_at).slice(0, 10);
      if (map.has(key)) {
        map.set(key, map.get(key) + (payment.amount || 0));
      }
    });
    return Array.from(map.entries()).map(([date, value]) => ({ date, value }));
  }, [paidPayments, range]);

  const signupsSeries = useMemo(() => {
    return events.slice(0, 6).map((event) => ({
      name: event.title,
      value: Number(event.attendees ?? 0),
    }));
  }, [events]);

  const recentPayments = useMemo(() => payments.slice(0, 5), [payments]);
  const recentClients = useMemo(
    () =>
      clients
        .filter((c) => c.lastActivity)
        .sort((a, b) => (a.lastActivity < b.lastActivity ? 1 : -1))
        .slice(0, 5),
    [clients]
  );
  const topCatalogItems = useMemo(() => catalogItems.slice(0, 3), [catalogItems]);

  return (
    <div className="space-y-6">
      {devNotice && <ErrorBanner message={devNotice} variant="info" />}
      {error && <ErrorBanner message={error} variant="error" />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{RU.labels.dashboardTitle}</h1>
          <p className="text-sm text-slate-500">{RU.labels.dashboardSubtitle}</p>
        </div>
        <div className="flex items-center gap-3">
          <Tabs
            tabs={[
              { label: "7д", value: "7d" },
              { label: "30д", value: "30d" },
              { label: "90д", value: "90d" },
            ]}
            active={range}
            onChange={setRange}
          />
          <Button variant="secondary">{RU.buttons.export}</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading
          ? Array.from({ length: 8 }).map((_, index) => <SkeletonCard key={index} rows={3} />)
          : dashboardStats.map((stat) => <DashboardStatCard key={stat.title} {...stat} />)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">{RU.labels.revenueOverTime}</h2>
            <span className="text-sm text-slate-500">{RU.labels.paid}</span>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={revenueSeries}>
                <defs>
                  <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Area type="monotone" dataKey="value" stroke="#6366f1" fill="url(#colorRevenue)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">{RU.labels.signupsByEvents}</h2>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={signupsSeries}>
                <XAxis dataKey="name" tick={false} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#0ea5e9" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <h2 className="text-lg font-semibold">{RU.labels.recentActivity}</h2>
          </CardHeader>
          <CardContent className="space-y-4">
            {recentPayments.map((payment) => (
              <div key={payment.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-700">
                  {RU.labels.payment} {payment.client_name || RU.messages.emDash} · {payment.event_title || RU.labels.noEvent}
                </span>
                <span className="text-slate-500">{formatCurrencyRub(payment.amount || 0)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">{RU.labels.botActivity}</h2>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentClients.map((client) => (
              <div key={client.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-700">{client.name}</span>
                <span className="text-slate-500">{client.lastActivity || RU.messages.emDash}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{RU.labels.getcourseWidget}</h2>
          <span className="text-sm text-slate-500">{getcourseSummary?.status || RU.statuses.disabled}</span>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm text-slate-700">
          <div>{RU.labels.getcourseCourses}: {getcourseSummary?.counts?.courses ?? 0}</div>
          <div>{RU.labels.getcourseProducts}: {getcourseSummary?.counts?.products ?? 0}</div>
          <div>{RU.labels.getcourseEvents}: {getcourseSummary?.counts?.events ?? 0}</div>
          <div>{RU.labels.getcourseCatalogItems}: {getcourseSummary?.counts?.catalog_items ?? 0}</div>
          <div>
            {RU.labels.getcourseLastSync}:{" "}
            {getcourseSummary?.lastSyncAt
              ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(new Date(getcourseSummary.lastSyncAt))
              : RU.messages.notSet}
          </div>
          <div>{RU.labels.getcourseCreated}: {getcourseSummary?.importedEvents?.created ?? getcourseSummary?.imported?.created ?? getcourseSummary?.counts?.created ?? 0}</div>
          <div>{RU.labels.getcourseUpdated}: {getcourseSummary?.importedEvents?.updated ?? getcourseSummary?.imported?.updated ?? getcourseSummary?.counts?.updated ?? 0}</div>
          <div>{RU.labels.getcourseSkipped}: {getcourseSummary?.importedEvents?.skipped ?? getcourseSummary?.imported?.skipped ?? getcourseSummary?.counts?.skipped ?? 0}</div>
          <div>{RU.labels.getcourseNoDate}: {getcourseSummary?.importedEvents?.no_date ?? getcourseSummary?.imported?.no_date ?? getcourseSummary?.counts?.no_date ?? 0}</div>
          <div>{RU.labels.getcourseCreated} ({RU.labels.getcourseImportedCatalog}): {getcourseSummary?.importedCatalog?.created ?? 0}</div>
          <div>{RU.labels.getcourseUpdated} ({RU.labels.getcourseImportedCatalog}): {getcourseSummary?.importedCatalog?.updated ?? 0}</div>
          <div>{RU.labels.getcourseSkipped} ({RU.labels.getcourseImportedCatalog}): {getcourseSummary?.importedCatalog?.skipped ?? 0}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">{RU.labels.dashboardCatalogTitle}</h2>
          <p className="text-sm text-slate-500">{RU.labels.dashboardCatalogHint}</p>
        </CardHeader>
        <CardContent className="space-y-3">
          {topCatalogItems.length === 0 ? (
            <div className="text-sm text-slate-500">{RU.labels.catalogEmpty}</div>
          ) : (
            topCatalogItems.map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-3 text-sm">
                <div>
                  <div className="font-medium text-slate-900">{item.title}</div>
                  <div className="text-slate-500">{item.price ? formatCurrencyRub(item.price) : RU.messages.notSet}</div>
                </div>
                {item.link_getcourse ? (
                  <a
                    href={item.link_getcourse}
                    target="_blank"
                    rel="noreferrer"
                    className="text-indigo-600 hover:text-indigo-700"
                  >
                    {RU.buttons.open}
                  </a>
                ) : (
                  <span className="text-slate-400">{RU.messages.notSet}</span>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
