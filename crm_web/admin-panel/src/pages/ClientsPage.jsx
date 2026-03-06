import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  createClient,
  deleteClient,
  getClients,
  requestClientContacts,
  setClientNeedsCall,
  updateClient,
} from "../api/clients";
import { useAuth } from "../auth/AuthContext";
import { RU, formatCurrencyRub, formatDateRu } from "../i18n/ru";
import ClientModal from "../components/ClientModal";
import EmptyState from "../components/EmptyState";
import SkeletonCard from "../components/SkeletonCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import Input from "../components/ui/Input";
import { Table, TBody, TD, TH, THead, TR } from "../components/ui/Table";

const STAGE_FILTER_ALL = "all";
const STAGE_FILTER_NEEDS_CALL = "needs_call";

const STAGE_FILTER_OPTIONS = [
  { value: STAGE_FILTER_ALL, label: "Все стадии" },
  { value: STAGE_FILTER_NEEDS_CALL, label: "Нужен звонок менеджера" },
  { value: "ENGAGED", label: "Общается с AI" },
  { value: "INACTIVE", label: "Холодный клиент" },
  { value: "MANAGER_FOLLOWUP", label: "Горячий клиент" },
  { value: "PAID", label: "Оплатил" },
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

function normalizeTag(tag) {
  return String(tag || "").trim().replace(/^#+/, "");
}

function normalizeTags(tags) {
  if (!Array.isArray(tags)) return [];
  const seen = new Set();
  const result = [];
  tags.forEach((value) => {
    const next = normalizeTag(value);
    if (!next) return;
    const key = next.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    result.push(next);
  });
  return result;
}

function hasClientSignupIndicator(client) {
  // TODO: Replace this heuristic with explicit registration/consultation flag from backend.
  return Boolean(client?.interested || client?.flags?.readyToPay);
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
  const [stageFilter, setStageFilter] = useState(STAGE_FILTER_ALL);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [modalError, setModalError] = useState("");

  const [editingTagsClientId, setEditingTagsClientId] = useState(null);
  const [editingTagsDraft, setEditingTagsDraft] = useState([]);
  const [newTagValue, setNewTagValue] = useState("");
  const [savingTagsClientId, setSavingTagsClientId] = useState(null);

  const [updatingCallClientId, setUpdatingCallClientId] = useState(null);

  const buildClientParams = useCallback((nextOffset) => {
    const params = {
      limit: CLIENTS_PAGE_SIZE,
      offset: nextOffset,
    };
    const normalizedQuery = query.trim();
    if (normalizedQuery) {
      params.search = normalizedQuery;
    }
    if (stageFilter === STAGE_FILTER_NEEDS_CALL) {
      params.needs_call = true;
    } else if (stageFilter !== STAGE_FILTER_ALL) {
      params.stage = stageFilter;
    }
    return params;
  }, [query, stageFilter]);

  const loadClientsPage = useCallback(async (nextOffset, { append }) => {
    const data = await getClients(buildClientParams(nextOffset));
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
  }, [buildClientParams]);

  const fetchClients = useCallback(async () => {
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
  }, [loadClientsPage]);

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
  }, [fetchClients]);

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

  const startEditingTags = (client) => {
    setEditingTagsClientId(client.id);
    setEditingTagsDraft(normalizeTags(client.tags));
    setNewTagValue("");
  };

  const stopEditingTags = () => {
    setEditingTagsClientId(null);
    setEditingTagsDraft([]);
    setNewTagValue("");
  };

  const addDraftTag = () => {
    const nextTag = normalizeTag(newTagValue);
    if (!nextTag) return;
    setEditingTagsDraft((prev) => normalizeTags([...prev, nextTag]));
    setNewTagValue("");
  };

  const removeDraftTag = (tagToRemove) => {
    const normalizedToRemove = normalizeTag(tagToRemove).toLowerCase();
    setEditingTagsDraft((prev) =>
      prev.filter((item) => normalizeTag(item).toLowerCase() !== normalizedToRemove)
    );
  };

  const handleTagInputKeyDown = (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    addDraftTag();
  };

  const handleSaveTags = async (client) => {
    if (!canManage) return;
    try {
      setSavingTagsClientId(client.id);
      setError("");
      const updated = await updateClient(client.id, { tags: editingTagsDraft });
      setClients((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      stopEditingTags();
    } catch (err) {
      setError(err?.message || "Не удалось сохранить теги.");
    } finally {
      setSavingTagsClientId(null);
    }
  };

  const handleDismissManagerCall = async (client) => {
    if (!canManage || !client?.needs_manager_call) return;
    try {
      setUpdatingCallClientId(client.id);
      setError("");
      const updated = await setClientNeedsCall(client.id, false);

      if (stageFilter === STAGE_FILTER_NEEDS_CALL) {
        await fetchClients();
      } else {
        setClients((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      }
    } catch (err) {
      setError(err?.message || "Не удалось снять отметку звонка.");
    } finally {
      setUpdatingCallClientId(null);
    }
  };

  return (
    <Card>
      <CardHeader className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">{RU.labels.clientsTitle}</h2>
          <p className="text-sm text-slate-500">{RU.labels.clientsSubtitle}</p>
        </div>

        <div className="flex w-full flex-col gap-3 lg:flex-row lg:items-end">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Поиск по имени, Telegram, tg_id, #тегу"
            className="h-11 w-full flex-1"
          />

          <label className="w-full text-sm font-medium text-slate-600 lg:w-72">
            <span className="mb-1 block">Стадия</span>
            <select
              className="h-11 w-full rounded-lg border-2 border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={stageFilter}
              onChange={(event) => setStageFilter(event.target.value)}
            >
              {STAGE_FILTER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
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
        ) : clients.length === 0 ? (
          <EmptyState
            title={RU.labels.noClientsFound}
            description={RU.labels.noClientsHint}
            actionLabel={canManage ? RU.buttons.addClient : undefined}
            onAction={canManage ? openCreateModal : undefined}
          />
        ) : (
          <div className="space-y-3">
            <div className="text-xs text-slate-500">
              {clients.length} / {clientsTotal || clients.length}
            </div>
            <div className="clients-table-scroll max-h-[calc(100vh-18rem)] overflow-y-auto overflow-x-auto pb-2">
              <Table
                wrapperClassName="w-[1880px] max-w-none overflow-visible"
                tableClassName="w-[1880px] min-w-[1880px] table-fixed"
              >
                <colgroup>
                  <col className="w-[280px]" />
                  <col className="w-[190px]" />
                  <col className="w-[260px]" />
                  <col className="w-[150px]" />
                  <col className="w-[150px]" />
                  <col className="w-[240px]" />
                  <col className="w-[80px]" />
                  <col className="w-[140px]" />
                  <col className="w-[110px]" />
                  <col className="w-[280px]" />
                </colgroup>
                <THead>
                  <TR>
                    <TH>{RU.labels.client}</TH>
                    <TH>{RU.labels.stage}</TH>
                    <TH>Хэштэг</TH>
                    <TH>{RU.labels.telegram}</TH>
                    <TH>{RU.labels.phone}</TH>
                    <TH>{RU.labels.email}</TH>
                    <TH>{RU.labels.aiChats}</TH>
                    <TH>{RU.labels.lastActivity}</TH>
                    <TH className="text-right">{RU.labels.revenue}</TH>
                    <TH className="w-[280px] min-w-[280px] whitespace-nowrap text-right">{RU.labels.actions}</TH>
                  </TR>
                </THead>
                <TBody>
                  {clients.map((client) => {
                    const displayTags = normalizeTags(client.tags);
                    const tagsEditorOpen = editingTagsClientId === client.id;
                    const hasSignupBadge = hasClientSignupIndicator(client);
                    const isSavingTags = savingTagsClientId === client.id;
                    const isUpdatingCall = updatingCallClientId === client.id;

                    return (
                      <TR key={client.id}>
                        <TD>
                          <div className="truncate font-medium text-slate-900">{client.name || RU.messages.notSet}</div>
                          <div className="truncate text-xs text-slate-500">tg_id: {client.tg_id ?? RU.messages.notSet}</div>
                          <div className="truncate text-xs text-slate-500">
                            {RU.labels.readyToPay}: {client.flags?.readyToPay ? "Да" : "Нет"}
                          </div>
                        </TD>
                        <TD>
                          <div className="flex flex-col gap-2">
                            <div className="flex flex-wrap items-center gap-1.5">
                              {client.needs_manager_call && (
                                <Badge variant="cancelled" className="border-red-200 bg-red-50 text-red-700">
                                  Нужен звонок менеджера
                                </Badge>
                              )}
                              <Badge variant="default">{client.stage || "NEW"}</Badge>
                            </div>
                            {client.needs_manager_call && canManage && (
                              <Button
                                variant="secondary"
                                className="h-7 w-fit whitespace-nowrap px-2.5 text-xs"
                                onClick={() => handleDismissManagerCall(client)}
                                disabled={isUpdatingCall}
                              >
                                {isUpdatingCall ? RU.messages.loading : "Снять звонок"}
                              </Button>
                            )}
                          </div>
                        </TD>
                        <TD>
                          <div className="space-y-2">
                            <div className="flex flex-wrap items-center gap-1.5">
                              {displayTags.length ? (
                                displayTags.map((tag) => (
                                  <Badge key={`${client.id}-${tag}`} variant="default" className="max-w-full">
                                    #{tag}
                                  </Badge>
                                ))
                              ) : (
                                <span className="text-xs text-slate-400">{RU.messages.notSet}</span>
                              )}
                              {hasSignupBadge && (
                                <Badge variant="cancelled" className="border-red-200 bg-red-50 text-red-700">
                                  Есть запись
                                </Badge>
                              )}
                            </div>

                            {canManage &&
                              (tagsEditorOpen ? (
                                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                                  <div className="mb-2 flex flex-wrap gap-1.5">
                                    {editingTagsDraft.length ? (
                                      editingTagsDraft.map((tag) => (
                                        <span
                                          key={`draft-${client.id}-${tag}`}
                                          className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-white px-2 py-0.5 text-xs text-slate-700"
                                        >
                                          #{tag}
                                          <button
                                            type="button"
                                            className="text-slate-400 transition-colors hover:text-red-600"
                                            onClick={() => removeDraftTag(tag)}
                                            aria-label={`Удалить тег ${tag}`}
                                          >
                                            ×
                                          </button>
                                        </span>
                                      ))
                                    ) : (
                                      <span className="text-xs text-slate-400">Добавьте первый тег</span>
                                    )}
                                  </div>

                                  <div className="flex gap-1.5">
                                    <Input
                                      value={newTagValue}
                                      onChange={(event) => setNewTagValue(event.target.value)}
                                      onKeyDown={handleTagInputKeyDown}
                                      placeholder="#game10"
                                      className="h-8 text-xs"
                                    />
                                    <Button
                                      variant="secondary"
                                      className="h-8 whitespace-nowrap px-2.5 text-xs"
                                      onClick={addDraftTag}
                                    >
                                      + тег
                                    </Button>
                                  </div>

                                  <div className="mt-2 flex justify-end gap-1.5">
                                    <Button
                                      variant="secondary"
                                      className="h-7 whitespace-nowrap px-2.5 text-xs"
                                      onClick={stopEditingTags}
                                      disabled={isSavingTags}
                                    >
                                      {RU.buttons.cancel}
                                    </Button>
                                    <Button
                                      className="h-7 whitespace-nowrap px-2.5 text-xs"
                                      onClick={() => handleSaveTags(client)}
                                      disabled={isSavingTags}
                                    >
                                      {isSavingTags ? RU.messages.loading : RU.buttons.save}
                                    </Button>
                                  </div>
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  className="text-xs font-medium text-indigo-600 transition-colors hover:text-indigo-700"
                                  onClick={() => startEditingTags(client)}
                                >
                                  Редактировать теги
                                </button>
                              ))}
                          </div>
                        </TD>
                        <TD>
                          <div className="truncate whitespace-nowrap" title={client.telegram || ""}>
                            {client.telegram || RU.messages.notSet}
                          </div>
                        </TD>
                        <TD className="whitespace-nowrap">{client.phone || RU.messages.notSet}</TD>
                        <TD>
                          <div className="truncate whitespace-nowrap" title={client.email || ""}>
                            {client.email || RU.messages.notSet}
                          </div>
                        </TD>
                        <TD className="whitespace-nowrap">{client.aiChats ?? 0}</TD>
                        <TD className="whitespace-nowrap">
                          {client.lastActivity
                            ? formatDateRu(client.lastActivity, { day: "2-digit", month: "2-digit", year: "numeric" })
                            : RU.messages.notSet}
                        </TD>
                        <TD className="whitespace-nowrap text-right font-semibold">{formatCurrencyRub(client.revenue)}</TD>
                        <TD className="w-[280px] min-w-[280px] text-right">
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
                    );
                  })}
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
