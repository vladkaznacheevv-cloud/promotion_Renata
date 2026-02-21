import { useEffect, useState } from "react";

import { getAiStats } from "../api/ai";
import { getClients } from "../api/clients";
import { RU } from "../i18n/ru";
import SkeletonCard from "../components/SkeletonCard";
import { Card, CardHeader, CardContent } from "../components/ui/Card";

export default function BotPage() {
  const [stats, setStats] = useState(null);
  const [clients, setClients] = useState([]);

  useEffect(() => {
    (async () => {
      const ai = await getAiStats();
      const clientData = await getClients();
      setStats(ai);
      setClients(clientData.items ?? clientData);
    })();
  }, []);

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
