import { useEffect, useState } from "react";
import { X } from "lucide-react";

const STATUS_OPTIONS = ["Новый", "В работе", "Клиент", "VIP Клиент"];

export default function ClientModal({ open, onClose, onSubmit, initialData, error }) {
  const [name, setName] = useState("");
  const [telegram, setTelegram] = useState("");
  const [status, setStatus] = useState("Новый");
  const [tgId, setTgId] = useState("");

  useEffect(() => {
    if (initialData) {
      setName(initialData.name || "");
      setTelegram(initialData.telegram || "");
      setStatus(initialData.status || "Новый");
      setTgId("");
    } else {
      setName("");
      setTelegram("");
      setStatus("Новый");
      setTgId("");
    }
  }, [initialData, open]);

  if (!open) return null;

  const handleSubmit = (event) => {
    event.preventDefault();
    const payload = {
      name: name.trim(),
      telegram: telegram.trim() || null,
      status,
      tg_id: tgId ? Number(tgId) : undefined,
    };
    onSubmit(payload);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-xl max-w-xl w-full mx-4">
        <form className="p-6 space-y-4" onSubmit={handleSubmit}>
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-gray-900">
              {initialData ? "Редактировать клиента" : "Добавить клиента"}
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
            Имя клиента
            <input
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </label>

          <label className="block text-sm font-medium text-gray-700">
            Telegram @username
            <input
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={telegram}
              onChange={(e) => setTelegram(e.target.value)}
              placeholder="@username"
            />
          </label>

          <label className="block text-sm font-medium text-gray-700">
            Telegram ID (если есть)
            <input
              type="number"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={tgId}
              onChange={(e) => setTgId(e.target.value)}
              placeholder="10001"
            />
          </label>

          <label className="block text-sm font-medium text-gray-700">
            Статус
            <select
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {STATUS_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
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
