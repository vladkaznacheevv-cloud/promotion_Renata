import { useEffect, useState } from "react";
import { X } from "lucide-react";

export default function EventFormModal({ open, onClose, onSubmit, initialData, error }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [date, setDate] = useState("");
  const [price, setPrice] = useState("");
  const [status, setStatus] = useState("active");

  useEffect(() => {
    if (initialData) {
      setTitle(initialData.title || "");
      setDescription(initialData.description || "");
      setLocation(initialData.location || "");
      setDate(initialData.date || "");
      setPrice(initialData.price ?? "");
      setStatus(initialData.status || "active");
    } else {
      setTitle("");
      setDescription("");
      setLocation("");
      setDate("");
      setPrice("");
      setStatus("active");
    }
  }, [initialData, open]);

  if (!open) return null;

  const handleSubmit = (event) => {
    event.preventDefault();
    const payload = {
      title: title.trim(),
      description: description.trim() || null,
      location: location.trim() || null,
      date: date || null,
      price: price === "" ? null : Number(price),
      status,
    };
    onSubmit(payload);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-xl max-w-xl w-full mx-4">
        <form className="p-6 space-y-4" onSubmit={handleSubmit}>
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-gray-900">
              {initialData ? "Редактировать мероприятие" : "Создать мероприятие"}
            </h2>
            <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg" type="button">
              <X className="h-5 w-5" />
            </button>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-700">
              {error}
            </div>
          )}

          <label className="block text-sm font-medium text-gray-700">
            Название
            <input
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </label>

          <label className="block text-sm font-medium text-gray-700">
            Дата
            <input
              type="date"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>

          <label className="block text-sm font-medium text-gray-700">
            Локация
            <input
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </label>

          <label className="block text-sm font-medium text-gray-700">
            Описание
            <textarea
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </label>

          <label className="block text-sm font-medium text-gray-700">
            Цена (₽)
            <input
              type="number"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              min="0"
              step="0.01"
            />
          </label>

          <label className="block text-sm font-medium text-gray-700">
            Статус
            <select
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="active">Активен</option>
              <option value="finished">Завершен</option>
            </select>
          </label>

          <div className="flex justify-end gap-3 pt-2">
            <button className="px-4 py-2 border border-gray-300 rounded-lg" type="button" onClick={onClose}>
              Отмена
            </button>
            <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700" type="submit">
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
