import { Eye, Edit } from "lucide-react";

const formatRuble = (value) => {
  if (value === null || value === undefined || value === "") return "—";
  const str = String(value);
  return str.includes("₽") ? str : `${str} ₽`;
};

export default function EventCard({ event, onSelect }) {
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
        <h3 className="font-medium text-gray-900">{event.title}</h3>
        <span
          className={`px-2 py-1 text-xs rounded-full ${
            event.status === "active" ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"
          }`}
        >
          {event.status === "active" ? "Активен" : "Завершен"}
        </span>
      </div>
      <p className="text-sm text-gray-500 mb-2">{event.description}</p>
      <div className="flex justify-between text-sm">
        <span className="text-gray-600">{event.attendees} участников</span>
        <span className="font-medium text-gray-900">{formatRuble(event.revenue)}</span>
      </div>
      <div className="flex justify-between items-center mt-3">
        <span className="text-xs text-gray-500">{event.date}</span>
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
            onClick={(e) => e.stopPropagation()}
          >
            <Edit className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
