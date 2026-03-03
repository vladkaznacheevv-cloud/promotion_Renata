import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createClient, deleteClient, getClients, requestClientContacts, updateClient } from "../api/clients";
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
  "PAID",
  "INACTIVE",
];
const CLIENTS_PAGE_SIZE = 25;

function humanizeRequestContactsError(err) {
  const detail = err?.payload?.detail;
  const detailText =
    typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => item?.msg || item?.message || "").filter(Boolean).join("; ")
        : "";

  const rawText = detailText || (typeof err?.message === "string" ? err.message : "");
  const lowered = rawText.toLowerCase();
  if (lowered.includes("telegram id") || lowered.includes("tg_id")) {
    return RU.messages.contactsRequestNoTgId;
  }
  if (detailText) {
    return `${RU.messages.contactsRequestFailed} ${detailText}`;
  }
  return RU.messages.contactsRequestFailed;
}

export default function ClientsPage() {
  const { currentUser } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const role = currentUser?.role || "viewer";
  const canManage = role === "admin" || role === "manager";

  const [clients, setClients] = useState([]);
  const [clientsTotal, setClientsTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [query, setQuery] = useState("");
  const [stageFilter, setStageFilter] = useState("all");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [modalError, setModalError] = useState("");

  const loadClientsPage = async (nextOffset, { append }) => {
    const data = await getClients({ limit: CLIENTS_PAGE_SIZE, offset: nextOffset });
    const items = data?.items ?? data ?? [];
    const total = Number(data?.total ?? items.length);
    const loaded = nextOffset + items.length;
    setClientsTotal(total);
    setOffset(loaded);
    setHasMore(loaded < total && items.length > 0);
    if (append) {
      setClients((prev) => [...prev, ...items]);
      return;
    }
    setClients(items);
  };

  const fetchClients = async () => {
    try {
      setLoading(true);
      setError("");
      setSuccess("");
      await loadClientsPage(0, { append: false });
    } catch (err) {
      setError(err?.message || RU.messages.clientsLoadError);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadMore = async () => {
    if (!hasMore || loadingMore) return;
    try {
      setLoadingMore(true);
      setError("");
      await loadClientsPage(offset, { append: true });
    } catch (err) {
      setError(err?.message || RU.messages.clientsLoadError);
    } finally {
      setLoadingMore(false);
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
        setClientsTotal((prev) => prev + 1);
      }

      closeModal();
    } catch (err) {
      setModalError(err?.message || RU.messages.clientSaveError);
    }
  };

  const handleRequestContacts = async (client) => {
    if (!canManage) return;
    try {
      setError("");
      setSuccess("");
      await requestClientContacts(client.id);
      setSuccess(RU.messages.contactsSavedInfo);
    } catch (err) {
      setError(humanizeRequestContactsError(err));
    }
  };

  const handleDeleteClient = async (client) => {
    if (!canManage) return;
    const confirmed = window.confirm("Удалить клиента? Действие необратимо.");
    if (!confirmed) return;

    try {
      setError("");
      setSuccess("");
      await deleteClient(client.id);
      if (editingClient?.id === client.id) {
        closeModal();
      }
      await fetchClients();
      setSuccess("Удалено");
    } catch (err) {
      setError(err?.payload?.detail || err?.message || "Не удалось удалить клиента.");
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h2 className="text-lg font-semibold">{RU.labels.clientsTitle}</h2>
          <p className="text-sm text-slate-500">{RU.labels.clientsSubtitle}</p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 xl:w-auto xl:flex-nowrap xl:justify-end">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={RU.labels.searchByClient}
            className="w-full min-w-[260px] xl:w-[360px] 2xl:w-[440px]"
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
        {success && (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {success}
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
          <div className="space-y-3">
            <div className="text-xs text-slate-500">
              {filteredClients.length} / {clientsTotal || filteredClients.length}
            </div>
            <div className="clients-table-scroll max-h-[calc(100vh-18rem)] overflow-y-auto overflow-x-auto pb-2">
              <Table
                wrapperClassName="w-max min-w-full overflow-visible"
                tableClassName="min-w-[1400px]"
              >
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
                    <TH className="w-[1%] whitespace-nowrap text-right">{RU.labels.actions}</TH>
                  </TR>
                </THead>
                <TBody>
                  {filteredClients.map((client) => (
                    <TR key={client.id}>
                      <TD>
                        <div className="font-medium text-slate-900">{client.name}</div>
                        <div className="text-xs text-slate-500">tg_id: {client.tg_id ?? RU.messages.notSet}</div>
                        <div className="text-xs text-slate-500">
                          {RU.labels.readyToPay}: {client.flags?.readyToPay ? "Да" : "Нет"}
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
                          <div className="flex flex-nowrap justify-end gap-1.5">
                            <Button variant="secondary" className="h-8 whitespace-nowrap px-2.5 text-xs" onClick={() => openEditModal(client)}>
                              {RU.buttons.edit}
                            </Button>
                            <Button
                              variant="secondary"
                              className="h-8 whitespace-nowrap px-2.5 text-xs"
                              onClick={() => handleRequestContacts(client)}
                            >
                              {RU.buttons.requestContacts}
                            </Button>
                            <Button variant="danger" className="h-8 whitespace-nowrap px-2.5 text-xs" onClick={() => handleDeleteClient(client)}>
                              {RU.buttons.delete}
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
            </div>
            {hasMore && (
              <div className="flex justify-center">
                <Button variant="secondary" onClick={handleLoadMore} disabled={loadingMore}>
                  {loadingMore ? RU.messages.loading : RU.buttons.loadMore}
                </Button>
              </div>
            )}
          </div>
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
