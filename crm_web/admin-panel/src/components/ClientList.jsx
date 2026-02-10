import { Crown, Edit, Trash2, UserPlus } from "lucide-react";
import EmptyState from "./EmptyState";
import SkeletonCard from "./SkeletonCard";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import { Card, CardHeader, CardContent } from "./ui/Card";

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

export default function ClientList({
  clients,
  onAdd,
  onEdit,
  onDelete,
  isLoading,
  canEdit = true,
  canDelete = true,
}) {
  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Клиенты</h2>
        {canEdit && (
          <Button onClick={onAdd} className="px-3 py-2">
            <UserPlus className="h-4 w-4" />
            Добавить
          </Button>
        )}
      </CardHeader>
      <CardContent>
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
                className="flex items-center justify-between rounded-xl border border-slate-200 p-3 hover:bg-slate-50"
              >
                <div className="flex items-center space-x-3">
                  <div className="h-10 w-10 rounded-full bg-indigo-50 flex items-center justify-center">
                    {client.status === "VIP Клиент" ? (
                      <Crown className="h-5 w-5 text-purple-600" />
                    ) : (
                      <span className="text-indigo-800 font-medium">{client.name?.charAt(0)}</span>
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-base font-semibold text-slate-900">{client.name}</p>
                      {client.status === "VIP Клиент" && <Badge variant="vip">VIP</Badge>}
                    </div>
                    <p className="text-sm text-slate-500">{client.telegram || "—"}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-base font-semibold text-slate-900">{formatCurrency(client.revenue)}</p>
                  <p className="text-xs text-slate-500">{client.aiChats ?? 0} AI запросов</p>
                  {(canEdit || canDelete) && (
                    <div className="mt-2 flex justify-end gap-2">
                      {canEdit && (
                        <button
                          className="p-1 text-slate-400 hover:text-indigo-600"
                          type="button"
                          onClick={() => onEdit(client)}
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                      )}
                      {canDelete && (
                        <button
                          className="p-1 text-slate-400 hover:text-red-600"
                          type="button"
                          onClick={() => onDelete(client)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Нет клиентов"
            actionLabel={canEdit ? "Добавить клиента" : undefined}
            onAction={canEdit ? onAdd : undefined}
          />
        )}
      </CardContent>
    </Card>
  );
}
