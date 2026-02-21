import { Edit, Trash2 } from "lucide-react";

import { RU, formatCurrencyRub, formatDateRu } from "../i18n/ru";
import { renderText } from "../utils/renderText";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import Modal from "./ui/Modal";

const isValidUrl = (value) => {
  if (!value) return false;
  try {
    new URL(value);
    return true;
  } catch {
    return false;
  }
};

const isOnlineConsultation = (event) => !event?.date;

export default function EventModal({
  event,
  onClose,
  onEdit,
  onDelete,
  canEdit = true,
  canDelete = true,
}) {
  if (!event) return null;

  const link = event.link_getcourse;
  const footer = canEdit || canDelete ? (
    <div className="flex gap-3">
      {canEdit && (
        <Button className="flex-1" onClick={onEdit}>
          <Edit className="h-4 w-4" />
          {RU.buttons.edit}
        </Button>
      )}
      {canDelete && (
        <Button className="flex-1" variant="danger" onClick={onDelete}>
          <Trash2 className="h-4 w-4" />
          {RU.buttons.delete}
        </Button>
      )}
    </div>
  ) : null;

  return (
    <Modal
      open={Boolean(event)}
      onClose={onClose}
      title={
        <div className="flex items-center gap-3">
          <span>{event.title}</span>
          <Badge variant={isOnlineConsultation(event) || event.status === "active" ? "active" : "finished"}>
            {isOnlineConsultation(event) || event.status === "active" ? RU.statuses.active : RU.statuses.finished}
          </Badge>
        </div>
      }
      footer={footer}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-slate-500">{RU.labels.eventType}</p>
            <p className="text-base font-semibold text-slate-900">
              {isOnlineConsultation(event) ? RU.labels.eventTypeOnlineConsultation : RU.labels.eventTypeEvent}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500">{RU.labels.date}</p>
            <p className="text-base font-semibold text-slate-900">
              {isOnlineConsultation(event)
                ? RU.labels.rollingEventDate
                : formatDateRu(event.date, { day: "2-digit", month: "long", year: "numeric" })}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500">{RU.labels.price}</p>
            <p className="text-base font-semibold text-slate-900">{formatCurrencyRub(event.price)}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">{RU.labels.eventParticipants}</p>
            <p className="text-base font-semibold text-slate-900">{Number(event.attendees ?? 0)}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">{RU.labels.revenue}</p>
            <p className="text-base font-semibold text-slate-900">{formatCurrencyRub(event.revenue)}</p>
          </div>
        </div>

        <div>
          <p className="text-sm text-slate-500">{RU.labels.eventDescription}</p>
          <p className="text-base font-medium text-slate-900 whitespace-pre-line">
            {renderText(event.description) || RU.messages.notSet}
          </p>
        </div>

        <div>
          <p className="text-sm text-slate-500">{RU.labels.location}</p>
          <p className="text-base font-medium text-slate-900">{event.location || RU.messages.notSet}</p>
        </div>

        <div>
          <p className="text-sm text-slate-500">{RU.labels.eventGetCourseLink}</p>
          {isValidUrl(link) ? (
            <a className="text-sm font-medium text-indigo-600 hover:underline" href={link} target="_blank" rel="noreferrer">
              {link}
            </a>
          ) : (
            <p className="text-base font-medium text-slate-900">{link || RU.messages.notSet}</p>
          )}
        </div>
      </div>
    </Modal>
  );
}
