import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import ClientsPage from "./pages/ClientsPage";
import EventsPage from "./pages/EventsPage";
import CatalogPage from "./pages/CatalogPage";
import RegistrationsPage from "./pages/RegistrationsPage";
import PaymentsPage from "./pages/PaymentsPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import BotPage from "./pages/BotPage";
import IntegrationsPage from "./pages/IntegrationsPage";
import SettingsPage from "./pages/SettingsPage";
import AppLayout from "./layout/AppLayout";
import { AuthProvider, useAuth } from "./auth/AuthContext";

function RequireRole({ role, children }) {
  const { currentUser } = useAuth();
  if (!currentUser) return <Navigate to="/" replace />;
  if (currentUser.role !== role) return <Navigate to="/" replace />;
  return children;
}

function AppContent() {
  const { isAuthenticated, loading, login } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-500">
        Загрузка...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onSubmit={login} />;
  }

  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/registrations" element={<RegistrationsPage />} />
          <Route
            path="/payments"
            element={
              <RequireRole role="admin">
                <PaymentsPage />
              </RequireRole>
            }
          />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/bot" element={<BotPage />} />
          <Route
            path="/integrations"
            element={<IntegrationsPage />}
          />
          <Route
            path="/settings"
            element={
              <RequireRole role="admin">
                <SettingsPage />
              </RequireRole>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
