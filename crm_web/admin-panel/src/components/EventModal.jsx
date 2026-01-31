import { X, Edit, BarChart3, Trash2 } from "lucide-react";

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

export default function EventModal({ event, onClose, onEdit, onDelete }) {
  if (!event) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-semibold text-gray-900">{event.title}</h2>
            <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg" type="button">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Тип</p>
                <p className="text-base font-semibold text-gray-900">{event.type}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Цена</p>
                <p className="text-base font-semibold text-gray-900">{formatCurrency(event.price)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Участников</p>
                <p className="text-base font-semibold text-gray-900">{Number(event.attendees ?? 0)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Выручка</p>
                <p className="text-base font-semibold text-gray-900">{formatCurrency(event.revenue)}</p>
              </div>
            </div>

            <div>
              <p className="text-sm text-gray-500">Описание</p>
              <p className="text-base font-medium text-gray-900">{event.description || "—"}</p>
            </div>

            <div>
              <p className="text-sm text-gray-500">Место проведения</p>
              <p className="text-base font-medium text-gray-900">{event.location || "—"}</p>
            </div>

            <div>
              <p className="text-sm text-gray-500">Дата</p>
              <p className="text-base font-medium text-gray-900">{formatDate(event.date)}</p>
            </div>

            <div className="flex space-x-3 pt-4">
              <button
                className="flex-1 bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700"
                type="button"
                onClick={onEdit}
              >
                <Edit className="h-4 w-4 inline mr-2" />
                Редактировать
              </button>
              <button className="flex-1 border border-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-50" type="button">
                <BarChart3 className="h-4 w-4 inline mr-2" />
                Статистика
              </button>
              <button
                className="flex-1 border border-red-300 text-red-600 py-2 px-4 rounded-lg hover:bg-red-50"
                type="button"
                onClick={onDelete}
              >
                <Trash2 className="h-4 w-4 inline mr-2" />
                Удалить
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
