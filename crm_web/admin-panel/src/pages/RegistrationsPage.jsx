import { useEffect, useState } from "react";
import { getEvents, getEventAttendees } from "../api/events";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "../components/ui/Table";
import SkeletonCard from "../components/SkeletonCard";
import Badge from "../components/ui/Badge";

export default function RegistrationsPage() {
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState("");
  const [attendees, setAttendees] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const data = await getEvents();
      const list = data.items ?? data;
      setEvents(list);
      if (list.length) {
        setSelectedEvent(list[0].id);
      }
    })();
  }, []);

  useEffect(() => {
    if (!selectedEvent) return;
    (async () => {
      setLoading(true);
      const data = await getEventAttendees(selectedEvent);
      setAttendees(data.items ?? data);
      setLoading(false);
    })();
  }, [selectedEvent]);

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Регистрации</h2>
          <p className="text-sm text-slate-500">Список участников по событию.</p>
        </div>
        <select
          className="h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm"
          value={selectedEvent}
          onChange={(e) => setSelectedEvent(Number(e.target.value))}
        >
          {events.map((event) => (
            <option key={event.id} value={event.id}>
              {event.title}
            </option>
          ))}
        </select>
      </CardHeader>
      <CardContent>
        {loading ? (
          <SkeletonCard rows={3} className="p-6" />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Клиент</TH>
                <TH>Статус</TH>
                <TH>Telegram</TH>
                <TH>AI</TH>
              </TR>
            </THead>
            <TBody>
              {attendees.map((client) => (
                <TR key={client.id}>
                  <TD>
                    <div className="font-medium text-slate-900">{client.name}</div>
                    <div className="text-xs text-slate-500">{client.lastActivity || "—"}</div>
                  </TD>
                  <TD>
                    <Badge variant={client.status === "VIP Клиент" ? "vip" : "default"}>
                      {client.status}
                    </Badge>
                  </TD>
                  <TD>{client.telegram || "—"}</TD>
                  <TD>{client.aiChats ?? 0}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
