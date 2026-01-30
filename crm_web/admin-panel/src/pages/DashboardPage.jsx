import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Bot,
  Calendar,
  Crown,
  DollarSign,
  ExternalLink,
  Menu,
  MessageSquare,
  Plus,
  Search,
  TrendingUp,
  UserPlus,
  Users,
} from "lucide-react";
import { getAiStats } from "../api/ai";
import { getClients } from "../api/clients";
import { getEvents } from "../api/events";
import BottomActions from "../components/BottomActions";
import ClientList from "../components/ClientList";
import DashboardStatCard from "../components/DashboardStatCard";
import ErrorBanner from "../components/ErrorBanner";
import EventCard from "../components/EventCard";
import EventModal from "../components/EventModal";
import LeftPanel from "../components/LeftPanel";

export default function DashboardPage() {
  const [showLeftPanel, setShowLeftPanel] = useState(false);
  const [showBottomPanel, setShowBottomPanel] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [clients, setClients] = useState([]);
  const [events, setEvents] = useState([]);
  const [aiStats, setAiStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        setLoading(true);
        const [clientsRes, eventsRes, aiRes] = await Promise.all([
          getClients(),
          getEvents(),
          getAiStats(),
        ]);

        if (!active) return;

        setClients(clientsRes.items ?? clientsRes);
        setEvents(eventsRes.items ?? eventsRes);
        setAiStats(aiRes);
      } catch (err) {
        if (!active) return;
        const rawMessage = err?.message || "";
        const message = rawMessage.includes("Failed to fetch")
          ? "Не удалось подключиться к API. Проверь, что backend запущен и VITE_API_BASE_URL указывает на http://127.0.0.1:8000."
          : rawMessage || "Ошибка загрузки данных";
        setError(message);
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const vipCount = useMemo(
    () => clients.filter((client) => client.status === "VIP Клиент").length,
    [clients]
  );

  const dashboardStats = useMemo(
    () => [
      {
        title: "Общая выручка",
        value: "1,875,000 ₽",
        change: "+15.3%",
        changeType: "positive",
        icon: <DollarSign className="h-6 w-6" />,
      },
      {
        title: "Активные клиенты",
        value: clients.length ? clients.length.toLocaleString("ru-RU") : "—",
        change: "+12.5%",
        changeType: "positive",
        icon: <Users className="h-6 w-6" />,
      },
      {
        title: "Мероприятий",
        value: events.length ? events.length.toLocaleString("ru-RU") : "—",
        change: "0%",
        changeType: "neutral",
        icon: <Calendar className="h-6 w-6" />,
      },
      {
        title: "AI ответов",
        value: aiStats?.totalResponses
          ? aiStats.totalResponses.toLocaleString("ru-RU")
          : "—",
        change: "+42.3%",
        changeType: "positive",
        icon: <Bot className="h-6 w-6" />,
      },
      {
        title: "VIP клиентов",
        value: vipCount ? vipCount.toLocaleString("ru-RU") : "—",
        change: "+25.1%",
        changeType: "positive",
        icon: <Crown className="h-6 w-6" />,
      },
      {
        title: "Конверсия",
        value: "38.4%",
        change: "+3.2%",
        changeType: "positive",
        icon: <TrendingUp className="h-6 w-6" />,
      },
    ],
    [aiStats, clients.length, events.length, vipCount]
  );

  const quickActions = useMemo(
    () => [
      { id: 1, title: "Добавить клиента", icon: <UserPlus className="h-5 w-5" />, color: "blue" },
      { id: 2, title: "Создать мероприятие", icon: <Plus className="h-5 w-5" />, color: "green" },
      { id: 3, title: "Ответить в боте", icon: <MessageSquare className="h-5 w-5" />, color: "purple" },
      { id: 4, title: "Проверить оплаты", icon: <DollarSign className="h-5 w-5" />, color: "yellow" },
      { id: 5, title: "Настроить AI", icon: <Bot className="h-5 w-5" />, color: "indigo" },
      { id: 6, title: "Экспорт данных", icon: <BarChart3 className="h-5 w-5" />, color: "gray" },
    ],
    []
  );

  if (loading) return <div className="p-6">Загрузка...</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6">
        <div className="p-6 bg-green-500 text-white rounded-2xl shadow-lg text-2xl tw-test">
          TAILWIND VISUAL TEST
        </div>
        <div className="flex min-h-screen">
        <div className="flex-1 flex flex-col">
          <header className="bg-white shadow-sm border-b border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <button
                  onClick={() => setShowLeftPanel((prev) => !prev)}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                  type="button"
                >
                  <Menu className="h-6 w-6 text-gray-600" />
                </button>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">Renata Promotion</h1>
                  <p className="text-gray-500">Центр управления</p>
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Поиск..."
                    className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <button
                  onClick={() => setShowBottomPanel((prev) => !prev)}
                  className="p-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
                  type="button"
                >
                  <Plus className="h-5 w-5" />
                </button>
              </div>
            </div>
          </header>

          <main className="flex-1 overflow-auto p-6">
            <ErrorBanner message={error} />
            <div className="mb-6 rounded-xl bg-green-100 p-6 text-green-900">
              Tailwind OK
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {dashboardStats.map((stat) => (
                <DashboardStatCard key={stat.title} {...stat} />
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              <ClientList clients={clients} />

              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">AI помощник Mimo</h2>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-3 bg-purple-50 rounded-lg">
                      <p className="text-2xl font-bold text-purple-900">
                        {aiStats?.totalResponses ?? "—"}
                      </p>
                      <p className="text-sm text-purple-600">Ответов</p>
                    </div>
                    <div className="text-center p-3 bg-green-50 rounded-lg">
                      <p className="text-2xl font-bold text-green-900">
                        {aiStats?.avgRating ?? "—"}/5
                      </p>
                      <p className="text-sm text-green-600">Рейтинг</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <h3 className="font-medium text-gray-900">Популярные вопросы:</h3>
                    {aiStats?.topQuestions?.length ? (
                      aiStats.topQuestions.map((q, index) => (
                        <div key={`${q.question}-${index}`} className="flex justify-between text-sm">
                          <span className="text-gray-600">{q.question}</span>
                          <span className="text-indigo-600 font-medium">{q.count}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-gray-500">Нет данных</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </main>

          <div className="bg-white border-t border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">Активные мероприятия</h2>
              <div className="flex space-x-2">
                <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors" type="button">
                  <Plus className="h-4 w-4 inline mr-2" />
                  Создать
                </button>
                <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50" type="button">
                  <BarChart3 className="h-4 w-4 inline mr-2" />
                  Аналитика
                </button>
              </div>
            </div>

            {events.length ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {events.map((event) => (
                  <EventCard key={event.id} event={event} onSelect={setSelectedEvent} />
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-gray-200 p-6 text-sm text-gray-500">
                Нет активных мероприятий.
              </div>
            )}
          </div>
        </div>
        </div>
      </div>

      {showLeftPanel && <LeftPanel onClose={() => setShowLeftPanel(false)} />}

      {showBottomPanel && (
        <BottomActions actions={quickActions} onClose={() => setShowBottomPanel(false)} />
      )}

      <EventModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />

      <footer className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 z-40">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <span className="text-sm text-gray-500">© 2026 Renata Promotion</span>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-sm text-gray-600">AI Mimo</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-sm text-gray-600">YooKassa</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Telegram Bot</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                <span className="text-sm text-gray-600">GetCourse (скоро)</span>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-500">v1.0.0</span>
            <button className="text-sm text-indigo-600 hover:text-indigo-800 flex items-center" type="button">
              <ExternalLink className="h-4 w-4 mr-1" />
              Документация
            </button>
          </div>
        </div>
      </footer>

      {(showLeftPanel || showBottomPanel) && (
        <div
          className="fixed inset-0 bg-black bg-opacity-25 z-40"
          onClick={() => {
            setShowLeftPanel(false);
            setShowBottomPanel(false);
          }}
        />
      )}
    </div>
  );
}
