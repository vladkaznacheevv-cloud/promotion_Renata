import { X, Edit, BarChart3, Trash2 } from "lucide-react";

const formatRuble = (value) => {
  if (value === null || value === undefined || value === "") return "—";
  const str = String(value);
  return str.includes("₽") ? str : `${str} ₽`;
};

export default function EventModal({ event, onClose }) {
  if (!event) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-900">{event.title}</h2>
            <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg" type="button">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Тип</p>
                <p className="font-medium">{event.type}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Цена</p>
                <p className="font-medium">{event.price}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Участников</p>
                <p className="font-medium">{event.attendees}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Выручка</p>
                <p className="font-medium">{formatRuble(event.revenue)}</p>
              </div>
            </div>

            <div>
              <p className="text-sm text-gray-500">Описание</p>
              <p className="font-medium">{event.description}</p>
            </div>

            <div>
              <p className="text-sm text-gray-500">Место проведения</p>
              <p className="font-medium">{event.location}</p>
            </div>

            <div>
              <p className="text-sm text-gray-500">Дата</p>
              <p className="font-medium">{event.date}</p>
            </div>

            <div className="flex space-x-3 pt-4">
              <button className="flex-1 bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700" type="button">
                <Edit className="h-4 w-4 inline mr-2" />
                Редактировать
              </button>
              <button className="flex-1 border border-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-50" type="button">
                <BarChart3 className="h-4 w-4 inline mr-2" />
                Статистика
              </button>
              <button className="flex-1 border border-red-300 text-red-600 py-2 px-4 rounded-lg hover:bg-red-50" type="button">
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
