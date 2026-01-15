import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Calendar, 
  DollarSign, 
  Settings, 
  MessageSquare, 
  Bot, 
  UserPlus, 
  Search, 
  ChevronDown, 
  ChevronUp,
  Plus,
  CheckCircle,
  XCircle,
  Star,
  Crown,
  Menu,
  X,
  ChevronRight,
  BarChart3,
  TrendingUp,
  Eye,
  Edit,
  Trash2,
  ExternalLink
} from 'lucide-react';

function App() {
  // Состояния для панелей
  const [showLeftPanel, setShowLeftPanel] = useState(false);
  const [showBottomPanel, setShowBottomPanel] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [clients, setClients] = useState([]);
  const [events, setEvents] = useState([]);
  const [aiStats, setAiStats] = useState({});

  // Фейковые данные
  useEffect(() => {
    const mockClients = [
      { 
        id: 1, 
        name: 'Анна Петрова', 
        telegram: '@anna_p', 
        status: 'VIP Клиент', 
        registered: '2026-01-05', 
        interested: 'Концерт "Ностальгия"',
        aiChats: 8,
        lastActivity: '2026-01-06',
        revenue: '15000'
      },
      { 
        id: 2, 
        name: 'Михаил Сидоров', 
        telegram: '@mike_sid', 
        status: 'В работе', 
        registered: '2026-01-04', 
        interested: 'Мастер-класс SMM',
        aiChats: 12,
        lastActivity: '2026-01-06',
        revenue: '0'
      },
      { 
        id: 3, 
        name: 'Екатерина Иванова', 
        telegram: '@ekat_ivan', 
        status: 'VIP Клиент', 
        registered: '2026-01-03', 
        interested: 'VIP-канал',
        aiChats: 15,
        lastActivity: '2026-01-05',
        revenue: '500'
      },
    ];
    
    const mockEvents = [
      { 
        id: 1, 
        title: '🎵 Концерт "Ностальгия"', 
        type: 'Концерт', 
        price: '1,000 ₽', 
        attendees: 248, 
        date: '25 января 2026', 
        status: 'active',
        description: 'Вечер хитов 90-х и 2000-х',
        location: 'Клуб "Метро"',
        revenue: '248,000'
      },
      { 
        id: 2, 
        title: '🎓 Мастер-класс по SMM', 
        type: 'Обучение', 
        price: 'Бесплатно', 
        attendees: 42, 
        date: '1 февраля 2026', 
        status: 'active',
        description: 'Онлайн обучение продвижению',
        location: 'Онлайн',
        revenue: '0'
      },
      { 
        id: 3, 
        title: '🎨 Арт-вечеринка', 
        type: 'Творчество', 
        price: '500 ₽', 
        attendees: 17, 
        date: '15 января 2026', 
        status: 'active',
        description: 'Рисование и музыка',
        location: 'Галерея "Арт"',
        revenue: '8,500'
      },
    ];

    const mockAiStats = {
      totalResponses: 3421,
      activeUsers: 1248,
      avgRating: 4.8,
      responseTime: 1.2,
      topQuestions: [
        { question: 'Когда следующий концерт?', count: 142 },
        { question: 'Как оплатить VIP канал?', count: 89 },
        { question: 'Есть ли скидки?', count: 67 },
      ]
    };

    setClients(mockClients);
    setEvents(mockEvents);
    setAiStats(mockAiStats);
  }, []);
  
  // Статистика дашборда
  const dashboardStats = [
    { 
      title: 'Общая выручка', 
      value: '1,875,000 ₽', 
      change: '+15.3%', 
      changeType: 'positive',
      icon: <DollarSign className="h-6 w-6" />
    },
    { 
      title: 'Активные клиенты', 
      value: '1,248', 
      change: '+12.5%', 
      changeType: 'positive',
      icon: <Users className="h-6 w-6" />
    },
    { 
      title: 'Мероприятий', 
      value: '4', 
      change: '0%', 
      changeType: 'neutral',
      icon: <Calendar className="h-6 w-6" />
    },
    { 
      title: 'AI ответов', 
      value: '3,421', 
      change: '+42.3%', 
      changeType: 'positive',
      icon: <Bot className="h-6 w-6" />
    },
    { 
      title: 'VIP клиентов', 
      value: '89', 
      change: '+25.1%', 
      changeType: 'positive',
      icon: <Crown className="h-6 w-6" />
    },
    { 
      title: 'Конверсия', 
      value: '38.4%', 
      change: '+3.2%', 
      changeType: 'positive',
      icon: <TrendingUp className="h-6 w-6" />
    },
  ];
  
  // Быстрые действия
  const quickActions = [
    { id: 1, title: 'Добавить клиента', icon: <UserPlus className="h-5 w-5" />, color: 'blue' },
    { id: 2, title: 'Создать мероприятие', icon: <Plus className="h-5 w-5" />, color: 'green' },
    { id: 3, title: 'Ответить в боте', icon: <MessageSquare className="h-5 w-5" />, color: 'purple' },
    { id: 4, title: 'Проверить оплаты', icon: <DollarSign className="h-5 w-5" />, color: 'yellow' },
    { id: 5, title: 'Настроить AI', icon: <Bot className="h-5 w-5" />, color: 'indigo' },
    { id: 6, title: 'Экспорт данных', icon: <BarChart3 className="h-5 w-5" />, color: 'gray' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 relative">
      {/* Главная область */}
      <div className="flex h-screen">
        {/* Центральная область - Дашборд */}
        <div className="flex-1 flex flex-col">
          {/* Заголовок */}
          <header className="bg-white shadow-sm border-b border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <button
                  onClick={() => setShowLeftPanel(!showLeftPanel)}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
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
                  onClick={() => setShowBottomPanel(!showBottomPanel)}
                  className="p-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
                >
                  <Plus className="h-5 w-5" />
                </button>
              </div>
            </div>
          </header>

          {/* Основной контент */}
          <main className="flex-1 overflow-auto p-6">
            {/* Статистические карточки */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {dashboardStats.map((stat, index) => (
                <div key={index} className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                      <p className="mt-2 text-2xl font-bold text-gray-900">{stat.value}</p>
                      <div className={`mt-2 flex items-center text-sm ${
                        stat.changeType === 'positive' ? 'text-green-600' : 
                        stat.changeType === 'negative' ? 'text-red-600' : 'text-gray-600'
                      }`}>
                        {stat.changeType === 'positive' && <ChevronUp className="h-4 w-4 mr-1" />}
                        {stat.changeType === 'negative' && <ChevronDown className="h-4 w-4 mr-1" />}
                        {stat.change}
                      </div>
                    </div>
                    <div className="text-indigo-600">
                      {stat.icon}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Графики и аналитика */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              {/* Последние клиенты */}
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Последние клиенты</h2>
                <div className="space-y-4">
                  {clients.slice(0, 5).map(client => (
                    <div key={client.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50">
                      <div className="flex items-center space-x-3">
                        <div className="h-10 w-10 rounded-full bg-indigo-100 flex items-center justify-center">
                          {client.status === 'VIP Клиент' ? (
                            <Crown className="h-5 w-5 text-purple-600" />
                          ) : (
                            <span className="text-indigo-800 font-medium">{client.name.charAt(0)}</span>
                          )}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{client.name}</p>
                          <p className="text-sm text-gray-500">{client.telegram}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium text-gray-900">{client.revenue} ₽</p>
                        <p className="text-xs text-gray-500">{client.aiChats} AI запросов</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* AI статистика */}
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Помощник Mimo</h2>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-3 bg-purple-50 rounded-lg">
                      <p className="text-2xl font-bold text-purple-900">{aiStats.totalResponses}</p>
                      <p className="text-sm text-purple-600">Ответов</p>
                    </div>
                    <div className="text-center p-3 bg-green-50 rounded-lg">
                      <p className="text-2xl font-bold text-green-900">{aiStats.avgRating}/5</p>
                      <p className="text-sm text-green-600">Рейтинг</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <h3 className="font-medium text-gray-900">Популярные вопросы:</h3>
                    {aiStats.topQuestions?.map((q, index) => (
                      <div key={index} className="flex justify-between text-sm">
                        <span className="text-gray-600">{q.question}</span>
                        <span className="text-indigo-600 font-medium">{q.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </main>

          {/* Нижняя область - Мероприятия */}
          <div className="bg-white border-t border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">Активные мероприятия</h2>
              <div className="flex space-x-2">
                <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors">
                  <Plus className="h-4 w-4 inline mr-2" />
                  Создать
                </button>
                <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
                  <BarChart3 className="h-4 w-4 inline mr-2" />
                  Аналитика
                </button>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {events.map(event => (
                <div 
                  key={event.id} 
                  className="border rounded-lg p-4 hover:border-indigo-300 transition-colors cursor-pointer"
                  onClick={() => setSelectedEvent(event)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium text-gray-900">{event.title}</h3>
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      event.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {event.status === 'active' ? 'Активен' : 'Завершен'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mb-2">{event.description}</p>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">{event.attendees} участников</span>
                    <span className="font-medium text-gray-900">{event.revenue} ₽</span>
                  </div>
                  <div className="flex justify-between items-center mt-3">
                    <span className="text-xs text-gray-500">{event.date}</span>
                    <div className="flex space-x-1">
                      <button className="p-1 text-gray-400 hover:text-indigo-600">
                        <Eye className="h-4 w-4" />
                      </button>
                      <button className="p-1 text-gray-400 hover:text-green-600">
                        <Edit className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Левая панель управления */}
      {showLeftPanel && (
        <div className="fixed inset-y-0 left-0 w-80 bg-white shadow-xl z-50 border-r border-gray-200">
          <div className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Управление</h2>
              <button
                onClick={() => setShowLeftPanel(false)}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <div className="space-y-6">
              {/* Быстрая навигация */}
              <div>
                <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">Навигация</h3>
                <div className="space-y-2">
                  {[
                    { name: 'Дашборд', icon: <BarChart3 className="h-4 w-4" /> },
                    { name: 'Клиенты', icon: <Users className="h-4 w-4" /> },
                    { name: 'Мероприятия', icon: <Calendar className="h-4 w-4" /> },
                    { name: 'Оплаты', icon: <DollarSign className="h-4 w-4" /> },
                  ].map((item, index) => (
                    <button key={index} className="w-full flex items-center px-3 py-2 text-left hover:bg-gray-50 rounded-lg">
                      <div className="mr-3 text-gray-400">{item.icon}</div>
                      <span className="text-gray-700">{item.name}</span>
                      <ChevronRight className="h-4 w-4 ml-auto text-gray-400" />
                    </button>
                  ))}
                </div>
              </div>

              {/* Последние действия */}
              <div>
                <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">Последние действия</h3>
                <div className="space-y-2">
                  {[
                    'Добавлен новый клиент',
                    'Обновлено мероприятие',
                    'Получен платеж 1500₽',
                    'AI ответил на вопрос'
                  ].map((action, index) => (
                    <div key={index} className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-700">{action}</p>
                      <p className="text-xs text-gray-500 mt-1">{index + 1} мин назад</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Настройки */}
              <div>
                <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">Настройки</h3>
                <div className="space-y-2">
                  <button className="w-full flex items-center px-3 py-2 text-left hover:bg-gray-50 rounded-lg">
                    <Settings className="h-4 w-4 mr-3 text-gray-400" />
                    <span className="text-gray-700">Интеграции</span>
                  </button>
                  <button className="w-full flex items-center px-3 py-2 text-left hover:bg-gray-50 rounded-lg">
                    <Bot className="h-4 w-4 mr-3 text-gray-400" />
                    <span className="text-gray-700">AI настройки</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Нижняя панель быстрых действий */}
      {showBottomPanel && (
        <div className="fixed bottom-0 left-0 right-0 bg-white shadow-xl z-50 border-t border-gray-200">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">Быстрые действия</h2>
              <button
                onClick={() => setShowBottomPanel(false)}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {quickActions.map(action => (
                <button
                  key={action.id}
                  className={`p-4 rounded-lg border-2 border-dashed border-gray-300 hover:border-${action.color}-400 hover:bg-${action.color}-50 transition-colors text-center`}
                >
                  <div className={`text-${action.color}-600 mb-2 flex justify-center`}>
                    {action.icon}
                  </div>
                  <span className="text-sm font-medium text-gray-700">{action.title}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно мероприятия */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900">{selectedEvent.title}</h2>
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Тип</p>
                    <p className="font-medium">{selectedEvent.type}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Цена</p>
                    <p className="font-medium">{selectedEvent.price}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Участников</p>
                    <p className="font-medium">{selectedEvent.attendees}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Выручка</p>
                    <p className="font-medium">{selectedEvent.revenue} ₽</p>
                  </div>
                </div>
                
                <div>
                  <p className="text-sm text-gray-500">Описание</p>
                  <p className="font-medium">{selectedEvent.description}</p>
                </div>
                
                <div>
                  <p className="text-sm text-gray-500">Место проведения</p>
                  <p className="font-medium">{selectedEvent.location}</p>
                </div>
                
                <div>
                  <p className="text-sm text-gray-500">Дата</p>
                  <p className="font-medium">{selectedEvent.date}</p>
                </div>
                
                <div className="flex space-x-3 pt-4">
                  <button className="flex-1 bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700">
                    <Edit className="h-4 w-4 inline mr-2" />
                    Редактировать
                  </button>
                  <button className="flex-1 border border-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-50">
                    <BarChart3 className="h-4 w-4 inline mr-2" />
                    Статистика
                  </button>
                  <button className="flex-1 border border-red-300 text-red-600 py-2 px-4 rounded-lg hover:bg-red-50">
                    <Trash2 className="h-4 w-4 inline mr-2" />
                    Удалить
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Футер с интеграциями */}
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
            <button className="text-sm text-indigo-600 hover:text-indigo-800 flex items-center">
              <ExternalLink className="h-4 w-4 mr-1" />
              Документация
            </button>
          </div>
        </div>
      </footer>

      {/* Оверлей для закрытия панелей */}
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

export default App;
