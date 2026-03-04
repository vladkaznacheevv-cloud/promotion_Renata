import { useEffect, useMemo, useState } from "react";
import { Bot, Calendar, DollarSign, TrendingUp, Users } from "lucide-react";
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

import { getClients } from "../api/clients";
import { getDashboardSummary } from "../api/dashboard";
import { getEvents } from "../api/events";
import { DEV_MOCKS, getDevFallbackUsed } from "../api/http";
import { getGetCourseEvents, getGetCourseSummary } from "../api/integrations";
import { getPayments } from "../api/payments";
import { getRevenueSummary } from "../api/revenue";
import { RU, formatCurrencyRub, formatDateRu } from "../i18n/ru";
import DashboardStatCard from "../components/DashboardStatCard";
import ErrorBanner from "../components/ErrorBanner";
import SkeletonCard from "../components/SkeletonCard";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Tabs } from "../components/ui/Tabs";

export default function DashboardPage() {
  const [clients, setClients] = useState([]);
  const [events, setEvents] = useState([]);
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [revenueSummary, setRevenueSummary] = useState(null);
  const [payments, setPayments] = useState([]);
  const [getcourseSummary, setGetcourseSummary] = useState(null);
  const [getcourseEvents, setGetcourseEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [devNotice, setDevNotice] = useState("");
  const [range, setRange] = useState("7d");
  const rangeDays = range === "30d" ? 30 : range === "90d" ? 90 : 7;

  const fetchData = async (days, withLoading = false) => {
    try {
      if (withLoading) setLoading(true);
      setError("");
      const [clientsRes, eventsRes, dashboardRes, revenueRes, paymentsRes, gcSummaryRes, gcEventsRes] =
        await Promise.all([
          getClients(),
          getEvents(),
          getDashboardSummary(days),
          getRevenueSummary(),
          getPayments(),
          getGetCourseSummary(),
          getGetCourseEvents(5),
        ]);

      setClients(clientsRes.items ?? clientsRes);
      setEvents(eventsRes.items ?? eventsRes);
      setDashboardSummary(dashboardRes);
      setRevenueSummary(revenueRes);
      setPayments(paymentsRes.items ?? paymentsRes);
      setGetcourseSummary(gcSummaryRes);
      setGetcourseEvents(gcEventsRes?.items ?? []);

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
      await fetchData(rangeDays, true);
    })();
    return () => {
      active = false;
    };
  }, [rangeDays]);

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
        value: formatCurrencyRub(dashboardSummary?.revenue_total ?? 0),
        change: "—",
        changeType: "neutral",
        icon: <DollarSign className="h-6 w-6" />,
      },
      {
        title: RU.labels.activeClients,
        value: clients.length ? clients.length.toLocaleString("ru-RU") : RU.messages.emDash,
        change: "—",
        changeType: "neutral",
        icon: <Users className="h-6 w-6" />,
      },
      {
        title: RU.labels.eventsCount,
        value: events.length ? events.length.toLocaleString("ru-RU") : RU.messages.emDash,
        change: "—",
        changeType: "neutral",
        icon: <Calendar className="h-6 w-6" />,
      },
      {
        title: RU.labels.aiResponses,
        value: (dashboardSummary?.ai_answers ?? 0).toLocaleString("ru-RU"),
        change: "—",
        changeType: "neutral",
        icon: <Bot className="h-6 w-6" />,
      },
      {
        title: RU.labels.stageNew,
        value: (dashboardSummary?.new_clients ?? 0).toLocaleString("ru-RU"),
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
        value: (dashboardSummary?.payments_count ?? 0).toLocaleString("ru-RU"),
        change: "—",
        changeType: "positive",
        icon: <TrendingUp className="h-6 w-6" />,
      },
    ],
    [clients.length, dashboardSummary, events.length, stageCounters]
  );

  const paidPayments = useMemo(() => payments.filter((p) => p.status === "paid"), [payments]);

  const revenueSeries = useMemo(() => {
    const days = rangeDays;
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
  }, [paidPayments, rangeDays]);

  const topEvents = useMemo(() => {
    const map = new Map();

    events.forEach((event) => {
      map.set(event.id, {
        event_id: event.id,
        title: event.title || RU.labels.noEvent,
        revenue: Number(event.revenue ?? 0),
        registrations: Number(event.attendees ?? 0),
        paidCount: 0,
        paymentCount: 0,
      });
    });

    (revenueSummary?.byEvents ?? []).forEach((item) => {
      const current = map.get(item.event_id) || {
        event_id: item.event_id,
        title: item.title || RU.labels.noEvent,
        revenue: 0,
        registrations: 0,
        paidCount: 0,
        paymentCount: 0,
      };
      current.revenue = Number(item.revenue ?? current.revenue ?? 0);
      map.set(item.event_id, current);
    });

    payments.forEach((payment) => {
      if (!payment.event_id) return;
      const current = map.get(payment.event_id) || {
        event_id: payment.event_id,
        title: payment.event_title || RU.labels.noEvent,
        revenue: 0,
        registrations: 0,
        paidCount: 0,
        paymentCount: 0,
      };
      current.paymentCount += 1;
      if (payment.status === "paid") {
        current.paidCount += 1;
        current.revenue += Number(payment.amount ?? 0);
      }
      map.set(payment.event_id, current);
    });

    const metrics = Array.from(map.values());
    const bySales = [...metrics]
      .filter((event) => event.revenue > 0 || event.paidCount > 0)
      .sort((a, b) => b.revenue - a.revenue || b.paidCount - a.paidCount)
      .slice(0, 5);

    const byLeads = [...metrics]
      .sort(
        (a, b) =>
          b.registrations - a.registrations || b.paymentCount - a.paymentCount || b.revenue - a.revenue
      )
      .slice(0, 5);

    return { bySales, byLeads };
  }, [events, payments, revenueSummary]);

  const signupsSeries = useMemo(() => {
    return topEvents.byLeads.slice(0, 6).map((event) => ({
      name: event.title,
      value: event.registrations > 0 ? event.registrations : event.paymentCount,
    }));
  }, [topEvents.byLeads]);

  const recentPayments = useMemo(() => payments.slice(0, 5), [payments]);
  const recentClients = useMemo(
    () =>
      clients
        .filter((c) => c.lastActivity)
        .sort((a, b) => (a.lastActivity < b.lastActivity ? 1 : -1))
        .slice(0, 5),
    [clients]
  );

  return (
    <div className="space-y-6">
      {devNotice && <ErrorBanner message={devNotice} variant="info" />}
      {error && <ErrorBanner message={error} variant="error" />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{RU.labels.dashboardTitle}</h1>
          <p className="text-sm text-slate-500">{RU.labels.dashboardSubtitle}</p>
        </div>
        <Tabs
          tabs={[
            { label: "7 дней", value: "7d" },
            { label: "30 дней", value: "30d" },
            { label: "90 дней", value: "90d" },
          ]}
          active={range}
          onChange={setRange}
        />
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
            <span className="text-sm text-slate-500">RUB</span>
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
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => formatCurrencyRub(value)} />
                <Tooltip formatter={(value) => formatCurrencyRub(value)} />
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">{RU.labels.topSales}</h2>
          </CardHeader>
          <CardContent className="space-y-3">
            {topEvents.bySales.length === 0 ? (
              <div className="text-sm text-slate-500">{RU.messages.notSet}</div>
            ) : (
              topEvents.bySales.map((event) => (
                <div key={event.event_id} className="flex items-center justify-between text-sm">
                  <span className="line-clamp-1 text-slate-700">{event.title}</span>
                  <span className="font-medium text-slate-900">{formatCurrencyRub(event.revenue)}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">{RU.labels.topEvents}</h2>
          </CardHeader>
          <CardContent className="space-y-3">
            {topEvents.byLeads.length === 0 ? (
              <div className="text-sm text-slate-500">{RU.messages.notSet}</div>
            ) : (
              topEvents.byLeads.map((event) => (
                <div key={event.event_id} className="flex items-center justify-between text-sm">
                  <span className="line-clamp-1 text-slate-700">{event.title}</span>
                  <span className="font-medium text-slate-900">
                    {(event.registrations > 0 ? event.registrations : event.paymentCount).toLocaleString("ru-RU")}
                  </span>
                </div>
              ))
            )}
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
        <CardContent className="space-y-4 text-sm text-slate-700">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>{RU.labels.getcourseEvents24h}: {getcourseSummary?.events_last_24h ?? 0}</div>
            <div>{RU.labels.getcourseEvents7d}: {getcourseSummary?.events_last_7d ?? 0}</div>
            <div>{RU.labels.getcourseEvents}: {getcourseSummary?.counts?.events ?? 0}</div>
            <div>
              {RU.labels.getcourseLastEventAt}: {" "}
              {getcourseSummary?.last_event_at
                ? formatDateRu(getcourseSummary.last_event_at, { dateStyle: "short", timeStyle: "short" })
                : RU.messages.notSet}
            </div>
          </div>

          <div>
            <h3 className="mb-2 font-medium text-slate-900">{RU.labels.getcourseLatestEvents}</h3>
            {getcourseEvents.length === 0 ? (
              <p className="text-slate-500">{RU.messages.notSet}</p>
            ) : (
              <div className="space-y-2">
                {getcourseEvents.map((item) => (
                  <div key={item.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-slate-900">{item.event_type || "unknown"}</div>
                      <div className="truncate text-xs text-slate-500">{item.user_email || RU.messages.notSet}</div>
                    </div>
                    <div className="text-right text-xs text-slate-500">
                      <div>{item.amount != null ? formatCurrencyRub(item.amount) : RU.messages.notSet}</div>
                      <div>
                        {item.received_at
                          ? formatDateRu(item.received_at, { dateStyle: "short", timeStyle: "short" })
                          : RU.messages.notSet}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
