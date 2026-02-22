import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createEvent, deleteEvent, getEvents, updateEvent } from "../api/events";
import { useAuth } from "../auth/AuthContext";
import { RU, formatCurrencyRub, formatDateRu, withTitle } from "../i18n/ru";
import { renderText } from "../utils/renderText";
import EmptyState from "../components/EmptyState";
import EventFormModal from "../components/EventFormModal";
import EventModal from "../components/EventModal";
import SkeletonCard from "../components/SkeletonCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import Input from "../components/ui/Input";
import { Table, TBody, TD, TH, THead, TR } from "../components/ui/Table";

const scheduleTypeOf = (event) => event?.schedule_type || (event?.date ? "one_time" : "rolling");
const isRolling = (event) => scheduleTypeOf(event) === "rolling";
const isRecurring = (event) => scheduleTypeOf(event) === "recurring";
const isOnlineConsultation = (event) => isRolling(event);

const statusLabel = (event) =>
  (isOnlineConsultation(event) || event?.status !== "finished") ? RU.statuses.active : RU.statuses.finished;

const eventTypeLabel = (event) => {
  if (isRecurring(event)) return RU.labels.scheduleTypeRecurring;
  if (isRolling(event)) return RU.labels.scheduleTypeRolling;
  return RU.labels.eventTypeEvent;
};

export default function EventsPage() {
  const { currentUser } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const role = currentUser?.role || "viewer";
  const canManage = role === "admin" || role === "manager";

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [selectedEvent, setSelectedEvent] = useState(null);
  const [editingEvent, setEditingEvent] = useState(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await getEvents();
      setEvents(data.items ?? data ?? []);
    } catch (err) {
      setError(err?.message || RU.messages.eventsLoadError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, []);

  useEffect(() => {
    if (searchParams.get("create") !== "1") return;

    if (canManage) {
      setEditingEvent(null);
      setFormError("");
      setIsFormOpen(true);
    }

    const next = new URLSearchParams(searchParams);
    next.delete("create");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, canManage]);

  const filteredEvents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return events.filter((event) => {
      const normalizedStatus = isRolling(event) ? "active" : event.status;
      if (statusFilter !== "all" && normalizedStatus !== statusFilter) return false;
      if (!normalizedQuery) return true;

      const haystack = [event.title, event.description, event.location]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });
  }, [events, query, statusFilter]);

  const openCreateModal = () => {
    setEditingEvent(null);
    setFormError("");
    setIsFormOpen(true);
  };

  const openEditModal = (event) => {
    setSelectedEvent(null);
    setEditingEvent(event);
    setFormError("");
    setIsFormOpen(true);
  };

  const closeFormModal = () => {
    setIsFormOpen(false);
    setEditingEvent(null);
    setFormError("");
  };

  const handleSubmitEvent = async (payload) => {
    try {
      setSubmitting(true);
      setFormError("");

      if (editingEvent) {
        const updated = await updateEvent(editingEvent.id, payload);
        setEvents((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        setSelectedEvent(updated);
      } else {
        const created = await createEvent(payload);
        setEvents((prev) => [created, ...prev]);
      }

      closeFormModal();
    } catch (err) {
      setFormError(err?.message || RU.messages.eventSaveError);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteEvent = async (event) => {
    if (!canManage) return;

    const confirmed = window.confirm(withTitle(RU.messages.deleteEventConfirm, event.title));
    if (!confirmed) return;

    try {
      await deleteEvent(event.id);
      setEvents((prev) => prev.filter((item) => item.id !== event.id));
      if (selectedEvent?.id === event.id) setSelectedEvent(null);
    } catch (err) {
      setError(err?.message || RU.messages.eventDeleteError);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold">{RU.labels.eventsTitle}</h2>
          <p className="text-sm text-slate-500">{RU.labels.eventsSubtitle}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={RU.labels.searchByEvent}
            className="min-w-[260px]"
          />

          <select
            className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">{RU.labels.allStatuses}</option>
            <option value="active">{RU.statuses.active}</option>
            <option value="finished">{RU.statuses.finished}</option>
          </select>

          {canManage && <Button onClick={openCreateModal}>{RU.buttons.createEvent}</Button>}
        </div>
      </CardHeader>

      <CardContent>
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <SkeletonCard rows={4} className="p-6" />
        ) : filteredEvents.length === 0 ? (
          <EmptyState
            title={RU.labels.noEventsFound}
            description={RU.labels.noEventsHint}
            actionLabel={canManage ? RU.buttons.createEvent : undefined}
            onAction={canManage ? openCreateModal : undefined}
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>{RU.labels.name}</TH>
                <TH>{RU.labels.eventType}</TH>
                <TH>{RU.labels.status}</TH>
                <TH>{RU.labels.date}</TH>
                <TH>{RU.labels.price}</TH>
                <TH>{RU.labels.location}</TH>
                <TH className="text-right">{RU.labels.actions}</TH>
              </TR>
            </THead>
            <TBody>
              {filteredEvents.map((event) => (
                <TR key={event.id}>
                  <TD>
                    <button type="button" className="text-left" onClick={() => setSelectedEvent(event)}>
                      <div className="font-medium text-slate-900">{event.title}</div>
                      <div className="text-xs text-slate-500 line-clamp-2">
                        {renderText(event.description) || RU.messages.notSet}
                      </div>
                    </button>
                  </TD>
                  <TD>
                    <div className="flex flex-col gap-1">
                      <span>{eventTypeLabel(event)}</span>
                      <Badge variant={isRecurring(event) ? "default" : isRolling(event) ? "active" : "default"}>
                        {isRecurring(event)
                          ? RU.labels.recurringBadge
                          : isRolling(event)
                            ? RU.labels.rollingBadge
                            : RU.labels.oneTimeBadge}
                      </Badge>
                    </div>
                  </TD>
                  <TD>
                    <Badge variant={statusLabel(event) === RU.statuses.active ? "active" : "finished"}>
                      {statusLabel(event)}
                    </Badge>
                  </TD>
                  <TD>
                    {isRecurring(event)
                      ? (event.schedule_text || RU.labels.recurringPresetTwiceMonth)
                      : isRolling(event)
                        ? RU.labels.rollingEventDate
                        : formatDateRu(event.date, { day: "2-digit", month: "2-digit", year: "numeric" })}
                  </TD>
                  <TD>{formatCurrencyRub(event.price)}</TD>
                  <TD>{event.location || RU.messages.notSet}</TD>
                  <TD className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button variant="secondary" onClick={() => setSelectedEvent(event)}>{RU.buttons.open}</Button>
                      {canManage && (
                        <Button variant="secondary" onClick={() => openEditModal(event)}>{RU.buttons.edit}</Button>
                      )}
                      {canManage && (
                        <Button variant="danger" onClick={() => handleDeleteEvent(event)}>{RU.buttons.delete}</Button>
                      )}
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </CardContent>

      <EventFormModal
        open={isFormOpen}
        onClose={closeFormModal}
        onSubmit={handleSubmitEvent}
        initialData={editingEvent}
        error={formError}
        submitting={submitting}
      />

      <EventModal
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
        onEdit={() => selectedEvent && openEditModal(selectedEvent)}
        onDelete={() => selectedEvent && handleDeleteEvent(selectedEvent)}
        canEdit={canManage}
        canDelete={canManage}
      />
    </Card>
  );
}
