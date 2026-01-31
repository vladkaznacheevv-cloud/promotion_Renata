import { Eye, Edit, Trash2 } from "lucide-react";

const formatCurrency = (value) => {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(num);
};

const formatDate = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(date);
};

export default function EventCard({ event, onSelect, onEdit, onDelete }) {
  const attendees = Number(event.attendees ?? 0);

  return (
    <div
      className="border rounded-lg p-4 hover:border-indigo-300 transition-colors cursor-pointer"
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
        <h3 className="text-base font-semibold text-gray-900">{event.title}</h3>
        <span
          className={`px-2 py-1 text-xs rounded-full ${
            event.status === "active" ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"
          }`}
        >
          {event.status === "active" ? "Активен" : "Завершен"}
        </span>
      </div>
      <p className="text-sm text-gray-500 mb-2">{event.description || "—"}</p>
      <div className="flex justify-between text-sm">
        <span className="text-gray-600">{Number.isFinite(attendees) ? attendees : 0} участников</span>
        <span className="text-sm font-semibold text-gray-900">{formatCurrency(event.revenue)}</span>
      </div>
      <div className="flex justify-between items-center mt-3">
        <span className="text-xs text-gray-500">{formatDate(event.date)}</span>
        <div className="flex space-x-1">
          <button
            className="p-1 text-gray-400 hover:text-indigo-600"
            type="button"
            onClick={(e) => e.stopPropagation()}
          >
            <Eye className="h-4 w-4" />
          </button>
          <button
            className="p-1 text-gray-400 hover:text-green-600"
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onEdit(event);
            }}
          >
            <Edit className="h-4 w-4" />
          </button>
          <button
            className="p-1 text-gray-400 hover:text-red-600"
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(event);
            }}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
