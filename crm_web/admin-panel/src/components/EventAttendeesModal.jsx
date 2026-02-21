import { RU } from "../i18n/ru";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import Modal from "./ui/Modal";

const statusVariant = (status) => {
  if (status === "VIP Клиент") return "vip";
  if (status === "Клиент") return "active";
  return "default";
};

export default function EventAttendeesModal({
  open,
  event,
  attendees,
  loading,
  error,
  onClose,
  onRemove,
  canRemove = true,
}) {
  if (!open || !event) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Участники — ${event.title}`}
      footer={
        <div className="flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            Закрыть
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        {loading ? (
          <p className="text-sm text-slate-500">Загрузка списка...</p>
        ) : attendees.length ? (
          <div className="space-y-3">
            {attendees.map((client) => (
              <div
                key={client.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-slate-900">{client.name}</p>
                    <Badge variant={statusVariant(client.status)}>{client.status}</Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    {client.telegram || RU.messages.emDash} • AI {client.aiChats ?? 0} • {client.lastActivity || RU.messages.emDash}
                  </p>
                </div>
                <Button variant="danger" onClick={() => onRemove(client)} className="text-xs" disabled={!canRemove}>
                  {RU.buttons.delete}
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Пока нет участников.</p>
        )}
      </div>
    </Modal>
  );
}
