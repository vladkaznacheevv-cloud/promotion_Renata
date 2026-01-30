import {
  BarChart3,
  Users,
  Calendar,
  DollarSign,
  Settings,
  Bot,
  ChevronRight,
  X,
} from "lucide-react";

const navigationItems = [
  { name: "Дашборд", icon: <BarChart3 className="h-4 w-4" /> },
  { name: "Клиенты", icon: <Users className="h-4 w-4" /> },
  { name: "Мероприятия", icon: <Calendar className="h-4 w-4" /> },
  { name: "Оплаты", icon: <DollarSign className="h-4 w-4" /> },
];

const recentActions = [
  "Добавлен новый клиент",
  "Обновлено мероприятие",
  "Получен платеж 1500₽",
  "AI ответил на вопрос",
];

export default function LeftPanel({ onClose }) {
  return (
    <div className="fixed inset-y-0 left-0 w-80 bg-white shadow-xl z-50 border-r border-gray-200">
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-900">Управление</h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg" type="button">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
              Навигация
            </h3>
            <div className="space-y-2">
              {navigationItems.map((item) => (
                <button
                  key={item.name}
                  className="w-full flex items-center px-3 py-2 text-left hover:bg-gray-50 rounded-lg"
                  type="button"
                >
                  <div className="mr-3 text-gray-400">{item.icon}</div>
                  <span className="text-gray-700">{item.name}</span>
                  <ChevronRight className="h-4 w-4 ml-auto text-gray-400" />
                </button>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
              Последние действия
            </h3>
            <div className="space-y-2">
              {recentActions.map((action, index) => (
                <div key={action} className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-700">{action}</p>
                  <p className="text-xs text-gray-500 mt-1">{index + 1} мин назад</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
              Настройки
            </h3>
            <div className="space-y-2">
              <button
                className="w-full flex items-center px-3 py-2 text-left hover:bg-gray-50 rounded-lg"
                type="button"
              >
                <Settings className="h-4 w-4 mr-3 text-gray-400" />
                <span className="text-gray-700">Интеграции</span>
              </button>
              <button
                className="w-full flex items-center px-3 py-2 text-left hover:bg-gray-50 rounded-lg"
                type="button"
              >
                <Bot className="h-4 w-4 mr-3 text-gray-400" />
                <span className="text-gray-700">AI настройки</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
