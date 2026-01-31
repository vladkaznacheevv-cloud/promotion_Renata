import { Crown, Edit, Trash2, UserPlus } from "lucide-react";
import EmptyState from "./EmptyState";
import SkeletonCard from "./SkeletonCard";

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

export default function ClientList({ clients, onAdd, onEdit, onDelete, isLoading }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Клиенты</h2>
        <button
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700"
          type="button"
          onClick={onAdd}
        >
          <UserPlus className="h-4 w-4" />
          Добавить
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((item) => (
            <SkeletonCard key={item} rows={2} className="p-4" />
          ))}
        </div>
      ) : clients.length ? (
        <div className="space-y-4">
          {clients.slice(0, 5).map((client) => (
            <div
              key={client.id}
              className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50"
            >
              <div className="flex items-center space-x-3">
                <div className="h-10 w-10 rounded-full bg-indigo-100 flex items-center justify-center">
                  {client.status === "VIP Клиент" ? (
                    <Crown className="h-5 w-5 text-purple-600" />
                  ) : (
                    <span className="text-indigo-800 font-medium">{client.name?.charAt(0)}</span>
                  )}
                </div>
                <div>
                  <p className="text-base font-semibold text-gray-900">{client.name}</p>
                  <p className="text-sm text-gray-500">{client.telegram || "—"}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-base font-semibold text-gray-900">{formatCurrency(client.revenue)}</p>
                <p className="text-xs text-gray-500">{client.aiChats ?? 0} AI запросов</p>
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    className="p-1 text-gray-400 hover:text-indigo-600"
                    type="button"
                    onClick={() => onEdit(client)}
                  >
                    <Edit className="h-4 w-4" />
                  </button>
                  <button
                    className="p-1 text-gray-400 hover:text-red-600"
                    type="button"
                    onClick={() => onDelete(client)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="Нет клиентов" actionLabel="Добавить клиента" onAction={onAdd} />
      )}
    </div>
  );
}
