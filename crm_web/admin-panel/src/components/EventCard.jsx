import { Users, Edit, Trash2 } from "lucide-react";

import { RU, formatCurrencyRub, formatDateRu } from "../i18n/ru";
import Badge from "./ui/Badge";

export default function EventCard({
  event,
  onSelect,
  onEdit,
  onDelete,
  onAttendees,
  canEdit = true,
  canDelete = true,
}) {
  const attendees = Number(event.attendees ?? 0);

  return (
    <div
      className="border border-slate-200 rounded-2xl p-4 shadow-sm bg-white hover:border-indigo-300 transition-colors cursor-pointer"
      onClick={() => onSelect(event)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          onSelect(event);
        }
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-base font-semibold text-slate-900">{event.title}</h3>
        <Badge variant={event.status === "active" ? "active" : "finished"}>
          {event.status === "active" ? RU.statuses.active : RU.statuses.finished}
        </Badge>
      </div>
      <p className="text-sm text-slate-500 mb-2">{event.description || RU.messages.emDash}</p>
      <div className="flex justify-between text-sm">
        <span className="text-slate-600">{Number.isFinite(attendees) ? attendees : 0} {RU.labels.eventParticipants.toLowerCase()}</span>
        <span className="text-sm font-semibold text-slate-900">{formatCurrencyRub(event.revenue)}</span>
      </div>
      <div className="flex justify-between items-center mt-3">
        <span className="text-xs text-slate-500">
          {formatDateRu(event.date, { day: "2-digit", month: "long", year: "numeric" })}
        </span>
        <div className="flex space-x-1">
          <button
            className="p-1 text-slate-400 hover:text-indigo-600"
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onAttendees?.(event);
            }}
            title={RU.labels.eventParticipants}
          >
            <Users className="h-4 w-4" />
          </button>
          {canEdit && (
            <button
              className="p-1 text-slate-400 hover:text-green-600"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onEdit(event);
              }}
              title={RU.buttons.edit}
            >
              <Edit className="h-4 w-4" />
            </button>
          )}
          {canDelete && (
            <button
              className="p-1 text-slate-400 hover:text-red-600"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(event);
              }}
              title={RU.buttons.delete}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
