import { useEffect, useState } from "react";

import { getGetCourseSummary, syncGetCourse } from "../api/integrations";
import { useAuth } from "../auth/AuthContext";
import { RU, formatDateRu } from "../i18n/ru";
import ErrorBanner from "../components/ErrorBanner";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import { Card, CardHeader, CardContent } from "../components/ui/Card";

function statusToLabel(status) {
  if (status === "OK") return RU.statuses.ok;
  if (status === "ERROR") return RU.statuses.error;
  return RU.statuses.disabled;
}

export default function IntegrationsPage() {
  const { currentUser } = useAuth();
  const role = currentUser?.role || "viewer";
  const isAdmin = role === "admin";

  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      setError("");
      const data = await getGetCourseSummary();
      setSummary(data);
    } catch (err) {
      setError(err?.message || RU.messages.integrationsLoadError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleSync = async () => {
    try {
      setSyncing(true);
      setError("");
      await syncGetCourse();
      await load();
    } catch (err) {
      setError(err?.message || RU.messages.integrationsSyncError);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} variant="error" />}
      <Card>
        <CardHeader className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{RU.labels.integrationsTitle}</h2>
            <p className="text-sm text-slate-500">{RU.labels.integrationsSubtitle}</p>
          </div>
          {isAdmin && (
            <Button onClick={handleSync} disabled={syncing || loading}>
              {syncing ? `${RU.buttons.sync}...` : RU.buttons.sync}
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {loading || !summary ? (
            <p className="text-sm text-slate-500">{RU.messages.loading}</p>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="font-medium text-slate-900">{RU.labels.getcourseWidget}</div>
                <Badge variant={summary.status === "OK" ? "active" : "default"}>
                  {statusToLabel(summary.status)}
                </Badge>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm text-slate-700">
                <div>{RU.labels.getcourseCourses}: {summary.counts?.courses ?? 0}</div>
                <div>{RU.labels.getcourseProducts}: {summary.counts?.products ?? 0}</div>
                <div>{RU.labels.getcourseEvents}: {summary.counts?.events ?? 0}</div>
              </div>
              <div className="text-sm text-slate-700">
                {RU.labels.getcourseCatalogItems}: {summary.counts?.catalog_items ?? 0}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm text-slate-700">
                <div>{RU.labels.getcourseFetched}: {summary.fetched ?? summary.counts?.fetched ?? 0}</div>
                <div>{RU.labels.getcourseCreated}: {summary.importedEvents?.created ?? summary.imported?.created ?? summary.counts?.created ?? 0}</div>
                <div>{RU.labels.getcourseUpdated}: {summary.importedEvents?.updated ?? summary.imported?.updated ?? summary.counts?.updated ?? 0}</div>
                <div>{RU.labels.getcourseSkipped}: {summary.importedEvents?.skipped ?? summary.imported?.skipped ?? summary.counts?.skipped ?? 0}</div>
              </div>
              <div className="text-sm text-slate-600">
                {RU.labels.getcourseNoDate}: {summary.importedEvents?.no_date ?? summary.imported?.no_date ?? summary.counts?.no_date ?? 0}
              </div>
              <div className="text-sm font-medium text-slate-700">{RU.labels.getcourseImportedCatalog}</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm text-slate-700">
                <div>{RU.labels.getcourseCreated}: {summary.importedCatalog?.created ?? 0}</div>
                <div>{RU.labels.getcourseUpdated}: {summary.importedCatalog?.updated ?? 0}</div>
                <div>{RU.labels.getcourseSkipped}: {summary.importedCatalog?.skipped ?? 0}</div>
              </div>
              <div className="text-sm text-slate-600">
                {RU.labels.getcourseLastSync}: {summary.lastSyncAt ? formatDateRu(summary.lastSyncAt, { dateStyle: "medium", timeStyle: "short" }) : RU.messages.notSet}
              </div>
              <div className="text-sm text-slate-600">
                {RU.labels.getcourseSource}: {summary.sourceUrl || RU.messages.notSet}
              </div>
              {summary.lastError && <div className="text-sm text-rose-600">{summary.lastError}</div>}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
