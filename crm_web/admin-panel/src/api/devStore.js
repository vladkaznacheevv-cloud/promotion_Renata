// Simple in-memory store for DEV_MOCKS mode.
let clientSeq = 3;
let eventSeq = 3;

const clients = [
  {
    id: 1,
    name: "Анна Петрова",
    telegram: "@anna_p",
    tg_id: 10001,
    phone: "+79991112233",
    email: "anna@example.com",
    stage: "PAID",
    status: "VIP Клиент",
    registered: "2026-01-05",
    interested: "Концерт \"Ностальгия\"",
    aiChats: 8,
    lastActivity: "2026-01-06",
    revenue: 15000,
  },
  {
    id: 2,
    name: "Михаил Сидоров",
    telegram: "@mike_sid",
    tg_id: 10002,
    phone: null,
    email: null,
    stage: "ENGAGED",
    status: "В работе",
    registered: "2026-01-04",
    interested: "Мастер-класс SMM",
    aiChats: 12,
    lastActivity: "2026-01-06",
    revenue: 0,
  },
  {
    id: 3,
    name: "Екатерина Иванова",
    telegram: "@ekat_ivan",
    tg_id: 10003,
    phone: "+79994445566",
    email: "ekat@example.com",
    stage: "READY_TO_PAY",
    status: "VIP Клиент",
    registered: "2026-01-03",
    interested: "VIP-канал",
    aiChats: 15,
    lastActivity: "2026-01-05",
    revenue: 500,
  },
];

const events = [
  {
    id: 1,
    title: "🎵 Концерт \"Ностальгия\"",
    type: "Концерт",
    price: 1000,
    attendees: 248,
    date: "2026-01-25",
    status: "active",
    description: "Вечер хитов 90-х и 2000-х",
    location: "Клуб \"Метро\"",
    link_getcourse: "https://example.com/course/nostalgia",
    revenue: 248000,
  },
  {
    id: 2,
    title: "🎓 Мастер-класс по SMM",
    type: "Обучение",
    price: 0,
    attendees: 42,
    date: "2026-02-01",
    status: "active",
    description: "Онлайн обучение продвижению",
    location: "Онлайн",
    link_getcourse: "https://example.com/course/smm",
    revenue: 0,
  },
  {
    id: 3,
    title: "🎨 Арт-вечеринка",
    type: "Творчество",
    price: 500,
    attendees: 17,
    date: "2026-01-15",
    status: "active",
    description: "Рисование и музыка",
    location: "Галерея \"Арт\"",
    link_getcourse: null,
    revenue: 8500,
  },
];

const catalogItems = [
  {
    id: 101,
    title: "Базовый курс по продажам",
    description: "Стартовый онлайн-курс для менеджеров по продажам.",
    price: 7900,
    currency: "RUB",
    link_getcourse: "https://example.com/getcourse/sales-basic",
    item_type: "course",
    status: "active",
    external_source: "getcourse",
    external_id: "gc-course-101",
    external_updated_at: "2026-02-07T10:00:00Z",
    updated_at: "2026-02-07T10:00:00Z",
  },
  {
    id: 102,
    title: "Практикум: упаковка оффера",
    description: "Набор материалов и шаблонов для подготовки офферов.",
    price: 3900,
    currency: "RUB",
    link_getcourse: "https://example.com/getcourse/offer-pack",
    item_type: "product",
    status: "active",
    external_source: "getcourse",
    external_id: "gc-product-102",
    external_updated_at: "2026-02-07T10:00:00Z",
    updated_at: "2026-02-07T10:00:00Z",
  },
  {
    id: 103,
    title: "Продвинутый курс по переговорам",
    description: "Онлайн-курс для тех, кто хочет повысить конверсию в сделку.",
    price: 11900,
    currency: "RUB",
    link_getcourse: "https://example.com/getcourse/negotiations-pro",
    item_type: "course",
    status: "active",
    external_source: "getcourse",
    external_id: "gc-course-103",
    external_updated_at: "2026-02-06T12:00:00Z",
    updated_at: "2026-02-06T12:00:00Z",
  },
];

const eventAttendees = {
  1: [1, 2],
  2: [3],
  3: [1],
};

let paymentSeq = 3;
const payments = [
  {
    id: 1,
    user_id: 1,
    client_name: "Анна Петрова",
    tg_id: 10001,
    event_id: 1,
    event_title: "🎵 Концерт \"Ностальгия\"",
    amount: 1500,
    currency: "RUB",
    status: "paid",
    source: "bot",
    created_at: "2026-01-05T10:00:00Z",
    paid_at: "2026-01-05T10:10:00Z",
  },
  {
    id: 2,
    user_id: 2,
    client_name: "Михаил Сидоров",
    tg_id: 10002,
    event_id: 2,
    event_title: "🎓 Мастер-класс по SMM",
    amount: 900,
    currency: "RUB",
    status: "pending",
    source: "bot",
    created_at: "2026-01-06T12:00:00Z",
    paid_at: null,
  },
  {
    id: 3,
    user_id: 3,
    client_name: "Екатерина Иванова",
    tg_id: 10003,
    event_id: 3,
    event_title: "🎨 Арт-вечеринка",
    amount: 500,
    currency: "RUB",
    status: "failed",
    source: "admin",
    created_at: "2026-01-04T09:00:00Z",
    paid_at: null,
  },
];

const aiStats = {
  totalResponses: 3421,
  activeUsers: clients.filter((c) => c.status !== "archived").length,
  avgRating: 4.8,
  responseTime: 1.2,
  topQuestions: [
    { question: "Когда следующий концерт?", count: 142 },
    { question: "Как оплатить VIP канал?", count: 89 },
    { question: "Есть ли скидки?", count: 67 },
  ],
};

let getcourseEvents = [
  {
    id: 1,
    received_at: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
    event_type: "payment",
    user_email: "test@example.com",
    deal_number: "D-1",
    amount: 100,
    currency: "RUB",
    status: "paid",
  },
];

let getcourseState = {
  enabled: true,
  has_key: false,
  base_url: "https://renataminakova.getcourse.ru",
  status: "OK",
  sourceUrl: "https://renataminakova.getcourse.ru",
  last_event_at: getcourseEvents[0].received_at,
  events_last_24h: getcourseEvents.length,
  events_last_7d: getcourseEvents.length,
  counts: {
    courses: 0,
    products: 0,
    events: getcourseEvents.length,
    catalog_items: 0,
    users: 0,
    payments: 0,
    fetched: getcourseEvents.length,
    created: 0,
    updated: 0,
    skipped: 0,
    no_date: 0,
    bad_url: 0,
  },
  ok: true,
  fetched: getcourseEvents.length,
  imported: { created: 0, updated: 0, skipped: 0, no_date: 0, bad_url: 0 },
  importedCatalog: { created: 0, updated: 0, skipped: 0, bad_url: 0 },
  importedUsers: { created: 0, updated: 0, skipped: 0 },
  importedPayments: { created: 0, updated: 0, skipped: 0 },
  lastError: null,
};

const clone = (value) => JSON.parse(JSON.stringify(value));

const deriveClient = (client) => {
  const stage = client.stage || "NEW";
  const phone = client.phone || null;
  const email = client.email || null;
  const readyToPay =
    Boolean(phone || email) || ["READY_TO_PAY", "MANAGER_FOLLOWUP", "PAID"].includes(stage);
  return {
    ...client,
    stage,
    phone,
    email,
    flags: {
      readyToPay,
      needsManager: stage === "MANAGER_FOLLOWUP",
    },
  };
};

export function getClients() {
  return { items: clone(clients.map(deriveClient)), total: clients.length };
}

export function createClient(payload) {
  clientSeq += 1;
  const now = new Date().toISOString().slice(0, 10);
  const client = {
    id: clientSeq,
    name: payload.name,
    telegram: payload.telegram || null,
    phone: payload.phone || null,
    email: payload.email || null,
    status: payload.status || "Новый",
    stage: payload.stage || (payload.phone || payload.email ? "READY_TO_PAY" : "NEW"),
    registered: now,
    interested: payload.interested || null,
    aiChats: 0,
    lastActivity: now,
    revenue: 0,
  };
  clients.unshift(client);
  aiStats.activeUsers = clients.filter((c) => c.status !== "archived").length;
  return clone(deriveClient(client));
}

export function updateClient(id, payload) {
  const idx = clients.findIndex((c) => c.id === id);
  if (idx === -1) return null;
  const next = { ...clients[idx], ...payload };
  if (payload.phone || payload.email) {
    next.stage = payload.stage || "READY_TO_PAY";
  }
  clients[idx] = next;
  aiStats.activeUsers = clients.filter((c) => c.status !== "archived").length;
  return clone(deriveClient(clients[idx]));
}

export function deleteClient(id) {
  const idx = clients.findIndex((c) => c.id === id);
  if (idx === -1) return false;
  clients.splice(idx, 1);
  aiStats.activeUsers = clients.filter((c) => c.status !== "archived").length;
  return true;
}

export function getEvents() {
  return { items: clone(events), total: events.length };
}

export function createEvent(payload) {
  eventSeq += 1;
  const event = {
    id: eventSeq,
    title: payload.title,
    type: payload.type || "Событие",
    price: payload.price ?? 0,
    attendees: payload.attendees ?? 0,
    date: payload.date || null,
    status: payload.status || "active",
    description: payload.description || null,
    location: payload.location || null,
    link_getcourse: payload.link_getcourse || null,
    revenue: payload.revenue ?? 0,
  };
  events.unshift(event);
  eventAttendees[event.id] = [];
  return clone(event);
}

export function updateEvent(id, payload) {
  const idx = events.findIndex((e) => e.id === id);
  if (idx === -1) return null;
  events[idx] = { ...events[idx], ...payload };
  return clone(events[idx]);
}

export function deleteEvent(id) {
  const idx = events.findIndex((e) => e.id === id);
  if (idx === -1) return false;
  events.splice(idx, 1);
  delete eventAttendees[id];
  return true;
}

export function getAiStats() {
  return clone(aiStats);
}

export function getEventAttendees(eventId) {
  const attendeeIds = eventAttendees[eventId] || [];
  const items = attendeeIds
    .map((id) => clients.find((client) => client.id === id))
    .filter(Boolean);
  return { items: clone(items), total: items.length };
}

export function addEventAttendee(eventId, payload) {
  const attendeeIds = eventAttendees[eventId] || [];
  const clientId = payload?.client_id ?? payload?.clientId;
  if (!clientId) return null;
  if (!attendeeIds.includes(clientId)) {
    attendeeIds.unshift(clientId);
  }
  eventAttendees[eventId] = attendeeIds;
  const event = events.find((e) => e.id === eventId);
  if (event) {
    event.attendees = attendeeIds.length;
  }
  const client = clients.find((c) => c.id === clientId);
  return clone(client || null);
}

export function removeEventAttendee(eventId, clientId) {
  const attendeeIds = eventAttendees[eventId] || [];
  const idx = attendeeIds.indexOf(clientId);
  if (idx === -1) return false;
  attendeeIds.splice(idx, 1);
  eventAttendees[eventId] = attendeeIds;
  const event = events.find((e) => e.id === eventId);
  if (event) {
    event.attendees = attendeeIds.length;
  }
  return true;
}

const buildRevenueSummary = () => {
  const paid = payments.filter((p) => p.status === "paid");
  const total = paid.reduce((sum, p) => sum + (p.amount || 0), 0);
  const byEventsMap = new Map();
  const byClientsMap = new Map();

  paid.forEach((p) => {
    if (p.event_id) {
      const current = byEventsMap.get(p.event_id) || {
        event_id: p.event_id,
        title: p.event_title || "—",
        revenue: 0,
      };
      current.revenue += p.amount || 0;
      byEventsMap.set(p.event_id, current);
    }
    const clientKey = p.user_id;
    const clientCurrent = byClientsMap.get(clientKey) || {
      user_id: p.user_id,
      name: p.client_name || "—",
      revenue: 0,
    };
    clientCurrent.revenue += p.amount || 0;
    byClientsMap.set(clientKey, clientCurrent);
  });

  return {
    total,
    paidCount: paid.length,
    pendingCount: payments.filter((p) => p.status === "pending").length,
    byEvents: Array.from(byEventsMap.values()).sort((a, b) => b.revenue - a.revenue),
    byClients: Array.from(byClientsMap.values()).sort((a, b) => b.revenue - a.revenue),
  };
};

export function getPayments() {
  return { items: clone(payments), total: payments.length };
}

export function createPayment(payload) {
  paymentSeq += 1;
  const client = clients.find((c) => c.id === payload.user_id);
  const event = events.find((e) => e.id === payload.event_id);
  const now = new Date().toISOString();
  const payment = {
    id: paymentSeq,
    user_id: payload.user_id,
    client_name: client?.name || "—",
    tg_id: client?.tg_id ?? null,
    event_id: payload.event_id ?? null,
    event_title: event?.title || null,
    amount: payload.amount,
    currency: payload.currency || "RUB",
    status: "pending",
    source: payload.source || "admin",
    created_at: now,
    paid_at: null,
  };
  payments.unshift(payment);
  return clone(payment);
}

export function updatePayment(id, payload) {
  const idx = payments.findIndex((p) => p.id === id);
  if (idx === -1) return null;
  const next = { ...payments[idx], ...payload };
  if (payload.status === "paid" && !next.paid_at) {
    next.paid_at = new Date().toISOString();
    const clientIdx = clients.findIndex((c) => c.id === next.user_id);
    if (clientIdx !== -1) {
      clients[clientIdx].stage = "PAID";
      clients[clientIdx].lastActivity = new Date().toISOString();
    }
  }
  payments[idx] = next;
  return clone(next);
}

export function getRevenueSummary() {
  return clone(buildRevenueSummary());
}

export function getGetCourseSummary() {
  getcourseState = {
    ...getcourseState,
    last_event_at: getcourseEvents.length ? getcourseEvents[0].received_at : null,
    events_last_24h: getcourseEvents.length,
    events_last_7d: getcourseEvents.length,
    counts: {
      ...getcourseState.counts,
      events: getcourseEvents.length,
      fetched: getcourseEvents.length,
    },
  };
  return clone(getcourseState);
}

export function getGetCourseEvents(limit = 50) {
  const rawLimit = typeof limit === "number" ? limit : 50;
  const safeLimit = Math.max(1, Math.min(Math.trunc(rawLimit), 100));
  const items = getcourseEvents.slice(0, safeLimit);
  return { items: clone(items), total: getcourseEvents.length };
}

export function getCatalog(params = {}) {
  const rawLimit = typeof params.limit === "number" ? params.limit : 50;
  const limit = Math.max(1, Math.min(Math.trunc(rawLimit), 100));
  const rawOffset = typeof params.offset === "number" ? params.offset : 0;
  const offset = Math.max(0, Math.trunc(rawOffset));
  const { type, search } = params;
  let items = [...catalogItems];

  if (type && type !== "all") {
    items = items.filter((item) => item.item_type === type);
  }
  if (search) {
    const pattern = String(search).trim().toLowerCase();
    if (pattern) {
      items = items.filter((item) =>
        [item.title, item.description].filter(Boolean).join(" ").toLowerCase().includes(pattern)
      );
    }
  }

  const total = items.length;
  const sliced = items.slice(offset, offset + limit);
  return { items: clone(sliced), total };
}

export function getCatalogItem(id) {
  const item = catalogItems.find((x) => x.id === Number(id));
  return item ? clone(item) : null;
}

export function syncGetCourse() {
  getcourseState = { ...getcourseState, status: "OK", lastError: null, ok: true };
  return clone(getcourseState);
}




