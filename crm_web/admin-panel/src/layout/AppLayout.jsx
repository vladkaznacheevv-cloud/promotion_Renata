import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Bot,
  Calendar,
  ChevronDown,
  CreditCard,
  LayoutDashboard,
  UserCircle2,
  Users,
  Workflow,
} from "lucide-react";

import { RU } from "../i18n/ru";
import { useAuth } from "../auth/AuthContext";
import Input from "../components/ui/Input";
import Badge from "../components/ui/Badge";
import HeaderActions from "./HeaderActions";

const navGroups = [
  {
    title: RU.nav.overview,
    items: [{ label: RU.nav.dashboard, to: "/", icon: <LayoutDashboard className="h-4 w-4" /> }],
  },
  {
    title: RU.nav.funnel,
    items: [
      { label: RU.nav.clients, to: "/clients", icon: <Users className="h-4 w-4" /> },
      { label: RU.nav.events, to: "/events", icon: <Calendar className="h-4 w-4" /> },
      { label: RU.nav.registrations, to: "/registrations", icon: <Workflow className="h-4 w-4" /> },
      { label: RU.nav.payments, to: "/payments", icon: <CreditCard className="h-4 w-4" /> },
    ],
  },
  {
    title: RU.nav.analytics,
    items: [
      { label: RU.nav.analytics, to: "/analytics", icon: <BarChart3 className="h-4 w-4" /> },
      { label: RU.nav.botActivity, to: "/bot", icon: <Bot className="h-4 w-4" /> },
    ],
  },
  {
    title: RU.nav.system,
    items: [
      { label: RU.nav.integrations, to: "/integrations", icon: <ChevronDown className="h-4 w-4" /> },
    ],
  },
];

export default function AppLayout({ children }) {
  const [collapsed, setCollapsed] = useState(false);
  const { currentUser, logout } = useAuth();
  const role = currentUser?.role || "viewer";
  const canManage = role === "admin" || role === "manager";
  const userDisplay =
    currentUser?.name ||
    currentUser?.username ||
    currentUser?.login ||
    currentUser?.email ||
    RU.messages.notSet;

  const filteredGroups = useMemo(() => {
    return navGroups.map((group) => ({
      ...group,
      items: group.items.filter((item) => (item.to === "/payments" ? role === "admin" : true)),
    }));
  }, [role]);

  const quickActions = useMemo(() => {
    const items = [];
    if (canManage) {
      items.push({ label: RU.buttons.addClient, to: "/clients?create=1" });
      items.push({ label: RU.buttons.createEvent, to: "/events?create=1" });
    }
    if (role === "admin") {
      items.push({ label: RU.buttons.createPayment, to: "/payments?create=1" });
    }
    return items;
  }, [canManage, role]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <aside
        className={`fixed inset-y-0 left-0 z-40 border-r border-slate-200 bg-white ${
          collapsed ? "w-20" : "w-64"
        } transition-all`}
      >
        <div className="flex items-center justify-between px-4 py-5">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-semibold">
              R
            </div>
            {!collapsed && <span className="font-semibold">Renata CRM</span>}
          </div>
          <button
            className="text-xs text-slate-400 hover:text-slate-700"
            onClick={() => setCollapsed((prev) => !prev)}
            type="button"
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>
        <nav className="px-3 pb-6 space-y-4">
          {filteredGroups.map((group) => (
            <div key={group.title}>
              {!collapsed && (
                <p className="px-3 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  {group.title}
                </p>
              )}
              <div className="space-y-1">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${
                        isActive
                          ? "bg-indigo-50 text-indigo-700"
                          : "text-slate-600 hover:bg-slate-100"
                      }`
                    }
                  >
                    <span className="text-slate-500">{item.icon}</span>
                    {!collapsed && <span>{item.label}</span>}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <div className={`${collapsed ? "pl-20" : "pl-64"} transition-all`}>
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur">
          <div className="mx-auto flex w-full max-w-[1760px] flex-col gap-3 px-4 py-3.5 lg:flex-row lg:items-center lg:justify-between lg:px-5">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <Input placeholder={RU.labels.search} className="max-w-[560px]" />
              <Badge variant="default">
                <UserCircle2 className="h-4 w-4" />
                {RU.labels.user}: {userDisplay}
              </Badge>
            </div>
            <HeaderActions items={quickActions} onLogout={logout} />
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1760px] px-4 py-6 lg:px-5 lg:py-7">{children}</main>
      </div>
    </div>
  );
}
