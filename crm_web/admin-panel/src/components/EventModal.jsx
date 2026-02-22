import { Edit, Trash2 } from "lucide-react";

import { RU, formatCurrencyRub, formatDateRu } from "../i18n/ru";
import { renderText } from "../utils/renderText";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import Modal from "./ui/Modal";

const scheduleTypeOf = (event) => event?.schedule_type || (event?.date ? "one_time" : "rolling");
const isOnlineConsultation = (event) => scheduleTypeOf(event) === "rolling";
const isRecurring = (event) => scheduleTypeOf(event) === "recurring";
const scheduleBadgeLabel = (event) => {
  if (isRecurring(event)) return RU.labels.recurringBadge;
  if (isOnlineConsultation(event)) return RU.labels.rollingBadge;
  return RU.labels.oneTimeBadge;
};

const pricingOptionsOf = (event) => {
  if (Array.isArray(event?.pricing_options) && event.pricing_options.length) {
    return event.pricing_options;
  }
  const legacy = [];
  if (event?.price_individual_rub != null) {
    legacy.push({ label: RU.labels.priceIndividualDisplay, price_rub: event.price_individual_rub, note: "" });
  }
  if (event?.price_group_rub != null) {
    legacy.push({ label: RU.labels.priceGroupDisplay, price_rub: event.price_group_rub, note: "за участника" });
  }
  if (legacy.length) return legacy;
  if (event?.price != null) {
    return [{ label: RU.labels.price, price_rub: event.price, note: "" }];
  }
  return [];
};

export default function EventModal({
  event,
  onClose,
  onEdit,
  onDelete,
  canEdit = true,
  canDelete = true,
}) {
  if (!event) return null;

  const pricingOptions = pricingOptionsOf(event);
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
          <Badge variant={isRecurring(event) ? "default" : isOnlineConsultation(event) ? "active" : "default"}>
            {scheduleBadgeLabel(event)}
          </Badge>
        </div>
      }
      footer={footer}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p className="text-sm text-slate-500">{RU.labels.eventType}</p>
            <p className="text-base font-semibold text-slate-900">
              {isRecurring(event)
                ? RU.labels.scheduleTypeRecurring
                : isOnlineConsultation(event)
                  ? RU.labels.scheduleTypeRolling
                  : RU.labels.eventTypeEvent}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500">{RU.labels.date}</p>
            <p className="text-base font-semibold text-slate-900">
              {isRecurring(event)
                ? (event.schedule_text || RU.labels.recurringPresetTwiceMonth)
                : isOnlineConsultation(event)
                ? RU.labels.rollingEventDate
                : formatDateRu(event.date, { day: "2-digit", month: "long", year: "numeric" })}
            </p>
          </div>
          <div className="sm:col-span-2">
            <p className="text-sm text-slate-500">{RU.labels.prices}</p>
            {pricingOptions.length ? (
              <div className="space-y-1 text-base font-semibold text-slate-900">
                {pricingOptions.map((option, index) => (
                  <p key={`${option.label}-${index}`}>
                    {option.label}: {formatCurrencyRub(option.price_rub)}
                    {option.note ? ` (${option.note})` : ""}
                  </p>
                ))}
              </div>
            ) : (
              <p className="text-base font-semibold text-slate-900">{RU.messages.notSet}</p>
            )}
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
          <p className="text-sm text-slate-500">{RU.labels.eventHosts}</p>
          <p className="text-base font-medium text-slate-900 whitespace-pre-line">
            {renderText(event.hosts) || RU.messages.notSet}
          </p>
        </div>

        <div>
          <p className="text-sm text-slate-500">{RU.labels.durationHint}</p>
          <p className="text-base font-medium text-slate-900 whitespace-pre-line">
            {renderText(event.duration_hint) || RU.messages.notSet}
          </p>
        </div>

        <div>
          <p className="text-sm text-slate-500">{RU.labels.bookingHint}</p>
          <p className="text-base font-medium text-slate-900 whitespace-pre-line">
            {renderText(event.booking_hint) || RU.messages.notSet}
          </p>
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

      </div>
    </Modal>
  );
}
