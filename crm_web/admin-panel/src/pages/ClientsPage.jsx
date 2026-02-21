import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createClient, getClients, updateClient } from "../api/clients";
import { useAuth } from "../auth/AuthContext";
import { RU, formatCurrencyRub, formatDateRu, stageLabel } from "../i18n/ru";
import ClientModal from "../components/ClientModal";
import EmptyState from "../components/EmptyState";
import SkeletonCard from "../components/SkeletonCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import Input from "../components/ui/Input";
import { Table, TBody, TD, TH, THead, TR } from "../components/ui/Table";

const STAGE_OPTIONS = [
  "NEW",
  "ENGAGED",
  "READY_TO_PAY",
  "MANAGER_FOLLOWUP",
  "PAID",
  "INACTIVE",
];

export default function ClientsPage() {
  const { currentUser } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const role = currentUser?.role || "viewer";
  const canManage = role === "admin" || role === "manager";

  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [query, setQuery] = useState("");
  const [stageFilter, setStageFilter] = useState("all");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [modalError, setModalError] = useState("");

  const fetchClients = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await getClients();
      setClients(data.items ?? data ?? []);
    } catch (err) {
      setError(err?.message || RU.messages.clientsLoadError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, []);

  useEffect(() => {
    if (searchParams.get("create") !== "1") return;

    if (canManage) {
      setEditingClient(null);
      setModalError("");
      setIsModalOpen(true);
    }

    const next = new URLSearchParams(searchParams);
    next.delete("create");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, canManage]);

  const filteredClients = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return clients.filter((client) => {
      if (stageFilter !== "all" && (client.stage || "NEW") !== stageFilter) return false;
      if (!normalizedQuery) return true;

      const haystack = [
        client.name,
        client.telegram,
        client.phone,
        client.email,
        client.tg_id ? String(client.tg_id) : "",
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });
  }, [clients, query, stageFilter]);

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingClient(null);
    setModalError("");
  };

  const openCreateModal = () => {
    setEditingClient(null);
    setModalError("");
    setIsModalOpen(true);
  };

  const openEditModal = (client) => {
    setEditingClient(client);
    setModalError("");
    setIsModalOpen(true);
  };

  const handleSubmitClient = async (payload) => {
    try {
      setModalError("");

      if (editingClient) {
        const updated = await updateClient(editingClient.id, payload);
        setClients((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      } else {
        const created = await createClient(payload);
        setClients((prev) => [created, ...prev]);
      }

      closeModal();
    } catch (err) {
      setModalError(err?.message || RU.messages.clientSaveError);
    }
  };

  const handleMarkManager = async (client) => {
    if (!canManage) return;
    try {
      const updated = await updateClient(client.id, { stage: "MANAGER_FOLLOWUP" });
      setClients((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setError(err?.message || RU.messages.stageUpdateError);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold">{RU.labels.clientsTitle}</h2>
          <p className="text-sm text-slate-500">{RU.labels.clientsSubtitle}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={RU.labels.searchByClient}
            className="min-w-[240px]"
          />

          <select
            className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700"
            value={stageFilter}
            onChange={(event) => setStageFilter(event.target.value)}
          >
            <option value="all">Все стадии</option>
            {STAGE_OPTIONS.map((stage) => (
              <option key={stage} value={stage}>
                {stageLabel(stage)}
              </option>
            ))}
          </select>

          {canManage && <Button onClick={openCreateModal}>{RU.buttons.addClient}</Button>}
        </div>
      </CardHeader>

      <CardContent>
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <SkeletonCard rows={4} className="p-6" />
        ) : filteredClients.length === 0 ? (
          <EmptyState
            title={RU.labels.noClientsFound}
            description={RU.labels.noClientsHint}
            actionLabel={canManage ? RU.buttons.addClient : undefined}
            onAction={canManage ? openCreateModal : undefined}
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>{RU.labels.client}</TH>
                <TH>{RU.labels.stage}</TH>
                <TH>{RU.labels.status}</TH>
                <TH>{RU.labels.telegram}</TH>
                <TH>{RU.labels.phone}</TH>
                <TH>{RU.labels.email}</TH>
                <TH>{RU.labels.aiChats}</TH>
                <TH>{RU.labels.lastActivity}</TH>
                <TH className="text-right">{RU.labels.revenue}</TH>
                <TH className="text-right">{RU.labels.actions}</TH>
              </TR>
            </THead>
            <TBody>
              {filteredClients.map((client) => (
                <TR key={client.id}>
                  <TD>
                    <div className="font-medium text-slate-900">{client.name}</div>
                    <div className="text-xs text-slate-500">tg_id: {client.tg_id ?? RU.messages.notSet}</div>
                    <div className="text-xs text-slate-500">
                      {RU.labels.readyToPay}: {client.flags?.readyToPay ? "Да" : "Нет"} · {RU.labels.needsManager}: {client.flags?.needsManager ? "Да" : "Нет"}
                    </div>
                  </TD>
                  <TD>
                    <Badge variant="default">{stageLabel(client.stage || "NEW")}</Badge>
                  </TD>
                  <TD>
                    <Badge variant={client.status === "VIP Клиент" ? "vip" : "default"}>{client.status}</Badge>
                  </TD>
                  <TD>{client.telegram || RU.messages.notSet}</TD>
                  <TD>{client.phone || RU.messages.notSet}</TD>
                  <TD>{client.email || RU.messages.notSet}</TD>
                  <TD>{client.aiChats ?? 0}</TD>
                  <TD>{client.lastActivity ? formatDateRu(client.lastActivity, { day: "2-digit", month: "2-digit", year: "numeric" }) : RU.messages.notSet}</TD>
                  <TD className="text-right font-semibold">{formatCurrencyRub(client.revenue)}</TD>
                  <TD className="text-right">
                    {canManage ? (
                      <div className="flex justify-end gap-2">
                        <Button variant="secondary" onClick={() => openEditModal(client)}>
                          {RU.buttons.edit}
                        </Button>
                        <Button variant="secondary" onClick={() => handleMarkManager(client)}>
                          {RU.buttons.markManagerFollowup}
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => window.alert(RU.messages.contactsSavedInfo)}
                        >
                          {RU.buttons.requestContacts}
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">{RU.labels.noAccess}</span>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </CardContent>

      <ClientModal
        open={isModalOpen}
        onClose={closeModal}
        onSubmit={handleSubmitClient}
        initialData={editingClient}
        error={modalError}
        role={role}
      />
    </Card>
  );
}
