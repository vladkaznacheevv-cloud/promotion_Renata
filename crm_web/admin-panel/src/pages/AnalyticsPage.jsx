import { useEffect, useState } from "react";

import { getRevenueSummary } from "../api/revenue";
import { RU, formatCurrencyRub } from "../i18n/ru";
import SkeletonCard from "../components/SkeletonCard";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "../components/ui/Table";

export default function AnalyticsPage() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    (async () => {
      const data = await getRevenueSummary();
      setSummary(data);
    })();
  }, []);

  if (!summary) {
    return <SkeletonCard rows={4} className="p-6" />;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">{RU.labels.analyticsTitle}</h2>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{formatCurrencyRub(summary.total || 0)}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">{RU.labels.topEvents}</h3>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>{RU.nav.events}</TH>
                <TH className="text-right">{RU.labels.revenue}</TH>
              </TR>
            </THead>
            <TBody>
              {summary.byEvents.map((row) => (
                <TR key={row.event_id}>
                  <TD>{row.title}</TD>
                  <TD className="text-right">{formatCurrencyRub(row.revenue || 0)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">{RU.labels.topClients}</h3>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>{RU.labels.client}</TH>
                <TH className="text-right">{RU.labels.revenue}</TH>
              </TR>
            </THead>
            <TBody>
              {summary.byClients.map((row) => (
                <TR key={row.user_id}>
                  <TD>{row.name}</TD>
                  <TD className="text-right">{formatCurrencyRub(row.revenue || 0)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
