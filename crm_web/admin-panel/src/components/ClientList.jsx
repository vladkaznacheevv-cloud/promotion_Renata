import { Crown } from "lucide-react";

const formatRuble = (value) => {
  if (value === null || value === undefined || value === "") return "—";
  const str = String(value);
  return str.includes("₽") ? str : `${str} ₽`;
};

export default function ClientList({ clients }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Последние клиенты</h2>
      {clients.length ? (
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
                  <p className="font-medium text-gray-900">{client.name}</p>
                  <p className="text-sm text-gray-500">{client.telegram}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">{formatRuble(client.revenue)}</p>
                <p className="text-xs text-gray-500">{client.aiChats} AI запросов</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-gray-200 p-4 text-sm text-gray-500">
          Клиенты не найдены.
        </div>
      )}
    </div>
  );
}
