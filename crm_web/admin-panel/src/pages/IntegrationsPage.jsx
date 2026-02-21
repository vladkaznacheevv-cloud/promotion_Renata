import { useEffect, useState } from "react";

import { getGetCourseEvents, getGetCourseSummary } from "../api/integrations";
import { RU, formatDateRu } from "../i18n/ru";
import ErrorBanner from "../components/ErrorBanner";
import Badge from "../components/ui/Badge";
import { Card, CardContent, CardHeader } from "../components/ui/Card";

function statusToLabel(status) {
  if (status === "OK") return RU.statuses.ok;
  if (status === "ERROR") return RU.statuses.error;
  return RU.statuses.disabled;
}

export default function IntegrationsPage() {
  const [summary, setSummary] = useState(null);
  const [eventsData, setEventsData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      setError("");
      const [summaryData, events] = await Promise.all([getGetCourseSummary(), getGetCourseEvents(50)]);
      setSummary(summaryData);
      setEventsData(events || { items: [], total: 0 });
    } catch (err) {
      setError(err?.message || RU.messages.integrationsLoadError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} variant="error" />}
      <Card>
        <CardHeader className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{RU.labels.integrationsTitle}</h2>
            <p className="text-sm text-slate-500">{RU.labels.integrationsSubtitle}</p>
          </div>
        </CardHeader>
        <CardContent>
          {loading || !summary ? (
            <p className="text-sm text-slate-500">{RU.messages.loading}</p>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="font-medium text-slate-900">{RU.labels.getcourseWidget}</div>
                <Badge variant={summary.status === "OK" ? "active" : "default"}>
                  {statusToLabel(summary.status)}
                </Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm text-slate-700">
                <div>{RU.labels.getcourseEvents24h}: {summary.events_last_24h ?? 0}</div>
                <div>{RU.labels.getcourseEvents7d}: {summary.events_last_7d ?? 0}</div>
                <div>{RU.labels.getcourseEvents}: {summary.counts?.events ?? 0}</div>
              </div>

              <div className="text-sm text-slate-700">
                {RU.labels.getcourseLastEventAt}:{" "}
                {summary.last_event_at
                  ? formatDateRu(summary.last_event_at, { dateStyle: "medium", timeStyle: "short" })
                  : RU.messages.notSet}
              </div>

              {summary.lastError && <div className="text-sm text-rose-600">{summary.lastError}</div>}

              <div>
                <div className="text-sm font-medium text-slate-800 mb-2">{RU.labels.getcourseLatestEvents}</div>
                <div className="overflow-x-auto border border-slate-200 rounded-lg">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="text-left px-3 py-2">Дата</th>
                        <th className="text-left px-3 py-2">Тип</th>
                        <th className="text-left px-3 py-2">Email</th>
                        <th className="text-left px-3 py-2">Сделка</th>
                        <th className="text-left px-3 py-2">Сумма</th>
                        <th className="text-left px-3 py-2">Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(eventsData.items || []).map((item) => (
                        <tr key={item.id} className="border-t border-slate-100">
                          <td className="px-3 py-2">
                            {item.received_at
                              ? formatDateRu(item.received_at, { dateStyle: "short", timeStyle: "short" })
                              : "—"}
                          </td>
                          <td className="px-3 py-2">{item.event_type || "unknown"}</td>
                          <td className="px-3 py-2">{item.user_email || "—"}</td>
                          <td className="px-3 py-2">{item.deal_number || "—"}</td>
                          <td className="px-3 py-2">{item.amount != null ? `${item.amount} ${item.currency || ""}` : "—"}</td>
                          <td className="px-3 py-2">{item.status || "—"}</td>
                        </tr>
                      ))}
                      {(!eventsData.items || eventsData.items.length === 0) && (
                        <tr>
                          <td className="px-3 py-3 text-slate-500" colSpan={6}>Нет событий</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
