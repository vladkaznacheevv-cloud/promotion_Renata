import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createClient, getClients } from "../api/clients";
import { getEvents } from "../api/events";
import { createPayment, getPayments, updatePayment } from "../api/payments";
import { useAuth } from "../auth/AuthContext";
import EmptyState from "../components/EmptyState";
import SkeletonCard from "../components/SkeletonCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import Input from "../components/ui/Input";
import { Table, TBody, TD, TH, THead, TR } from "../components/ui/Table";
import { RU, formatCurrencyRub, formatDateRu } from "../i18n/ru";

const statusVariant = (status) => {
  if (status === "paid") return "paid";
  if (status === "pending") return "pending";
  if (status === "cancelled") return "cancelled";
  return "finished";
};

const statusLabel = (status) => {
  if (status === "paid") return RU.statuses.paid;
  if (status === "pending") return RU.statuses.pending;
  if (status === "cancelled") return RU.statuses.cancelled;
  if (status === "finished") return RU.statuses.finished;
  if (status === "active") return RU.statuses.active;
  if (status === "failed") return RU.statuses.failed;
  return status;
};

function normalizeTelegram(value) {
  return String(value || "").trim().replace(/^@+/, "").toLowerCase();
}

function normalizeEmail(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizePhone(value) {
  const digits = String(value || "").replace(/\D+/g, "");
  if (digits.length === 11 && digits.startsWith("8")) {
    return `7${digits.slice(1)}`;
  }
  return digits;
}

function normalizeLookup(field, value) {
  if (field === "phone") return normalizePhone(value);
  if (field === "email") return normalizeEmail(value);
  return normalizeTelegram(value);
}

function matchesStrict(field, client, needle) {
  if (field === "phone") {
    return normalizePhone(client?.phone) === needle;
  }
  if (field === "email") {
    return normalizeEmail(client?.email) === needle;
  }
  return normalizeTelegram(client?.telegram) === needle;
}

function formatExistingClientOption(client) {
  const name = String(client?.name || "").trim() || "\u0411\u0435\u0437 \u0438\u043c\u0435\u043d\u0438";
  const parts = [name];
  const telegram = normalizeTelegram(client?.telegram);
  const phone = normalizePhone(client?.phone);
  const email = normalizeEmail(client?.email);
  if (telegram) parts.push(`@${telegram}`);
  if (phone) parts.push(phone);
  if (email) parts.push(email);
  return parts.join(" \u2022 ");
}

const UI_TEXT = {
  lookupRequired: "\u0423\u043a\u0430\u0436\u0438\u0442\u0435 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435 \u0434\u043b\u044f \u043f\u043e\u0438\u0441\u043a\u0430",
  clientNotFound: "\u041a\u043b\u0438\u0435\u043d\u0442 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d",
  findClientFirst: "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043d\u0430\u0439\u0434\u0438\u0442\u0435 \u043a\u043b\u0438\u0435\u043d\u0442\u0430",
  chooseClientFromList: "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043a\u043b\u0438\u0435\u043d\u0442\u0430 \u0438\u0437 \u0441\u043f\u0438\u0441\u043a\u0430",
  amountInvalid: "\u0421\u0443\u043c\u043c\u0430 \u0434\u043e\u043b\u0436\u043d\u0430 \u0431\u044b\u0442\u044c \u0446\u0435\u043b\u044b\u043c \u0447\u0438\u0441\u043b\u043e\u043c \u0431\u043e\u043b\u044c\u0448\u0435 0",
  nameRequired: "\u0423\u043a\u0430\u0436\u0438\u0442\u0435 \u0438\u043c\u044f \u043a\u043b\u0438\u0435\u043d\u0442\u0430",
  cashSource: "\u043d\u0430\u043b\u0438\u0447\u043a\u0430",
  createTitle: "\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u043b\u0430\u0442\u0435\u0436 (\u043d\u0430\u043b\u0438\u0447\u043a\u0430)",
  createSubtitle: "\u0421\u0442\u0430\u0442\u0443\u0441 \u0431\u0443\u0434\u0435\u0442 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d \u043a\u0430\u043a \u043e\u043f\u043b\u0430\u0447\u0435\u043d\u043e \u043f\u043e\u0441\u043b\u0435 \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u044f.",
  cancel: "\u041e\u0442\u043c\u0435\u043d\u0430",
  clientExists: "\u041a\u043b\u0438\u0435\u043d\u0442 \u0443\u0436\u0435 \u0435\u0441\u0442\u044c \u0432 \u0431\u0430\u0437\u0435?",
  yes: "\u0414\u0430",
  no: "\u041d\u0435\u0442",
  name: "\u0418\u043c\u044f",
  namePlaceholder: "\u0418\u043c\u044f \u043a\u043b\u0438\u0435\u043d\u0442\u0430",
  phoneOptional: "\u0422\u0435\u043b\u0435\u0444\u043e\u043d (\u043e\u043f\u0446\u0438\u043e\u043d\u0430\u043b\u044c\u043d\u043e)",
  telegramOptional: "Telegram username (\u043e\u043f\u0446\u0438\u043e\u043d\u0430\u043b\u044c\u043d\u043e)",
  lookupBy: "\u0418\u0441\u043a\u0430\u0442\u044c \u043f\u043e",
  lookupTelegram: "Telegram username (@nick)",
  lookupPhone: "\u0422\u0435\u043b\u0435\u0444\u043e\u043d",
  lookupEmail: "Email",
  lookupValue: "\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u0435",
  lookupTelegramPlaceholder: "@nickname",
  lookupPhonePlaceholder: "+7 (999) 123-45-67",
  lookupEmailPlaceholder: "name@example.com",
  find: "\u041d\u0430\u0439\u0442\u0438",
  chooseClient: "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043a\u043b\u0438\u0435\u043d\u0442\u0430",
  event: "\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435",
  noEvent: "\u0411\u0435\u0437 \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044f",
  amount: "\u0421\u0443\u043c\u043c\u0430",
  paidStatus: "\u0421\u0442\u0430\u0442\u0443\u0441: \u041e\u043f\u043b\u0430\u0447\u0435\u043d\u043e",
  sourceLine: "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a: \u043d\u0430\u043b\u0438\u0447\u043a\u0430",
  dateLine: "\u0414\u0430\u0442\u0430: \u0442\u0435\u043a\u0443\u0449\u0430\u044f",
  create: "\u0421\u043e\u0437\u0434\u0430\u0442\u044c",
};

export default function PaymentsPage({ clients = [], events = [], role }) {
  const auth = useAuth();
  const effectiveRole = role || auth.currentUser?.role || "viewer";
  const canManagePayments = effectiveRole === "admin";
  const [searchParams, setSearchParams] = useSearchParams();

  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [statusFilter, setStatusFilter] = useState("");
  const [eventFilter, setEventFilter] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  const [search, setSearch] = useState("");

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [modalError, setModalError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [createMode, setCreateMode] = useState("existing");
  const [existingLookupField, setExistingLookupField] = useState("telegram");
  const [existingLookupValue, setExistingLookupValue] = useState("");
  const [existingMatches, setExistingMatches] = useState([]);
  const [selectedExistingClientId, setSelectedExistingClientId] = useState("");
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newTelegram, setNewTelegram] = useState("");
  const [createEventId, setCreateEventId] = useState("");
  const [createAmount, setCreateAmount] = useState("");
  const [modalEvents, setModalEvents] = useState([]);
  const [modalEventsLoaded, setModalEventsLoaded] = useState(false);

  const loadModalEvents = useCallback(async () => {
    try {
      const data = await getEvents();
      const items = data?.items ?? data ?? [];
      const activeSorted = items
        .filter((eventItem) => eventItem?.status === "active")
        .sort((a, b) =>
          String(a?.title || "").localeCompare(String(b?.title || ""), "ru"),
        );
      setModalEvents(activeSorted);
    } catch (_error) {
      setModalEvents([]);
    } finally {
      setModalEventsLoaded(true);
    }
  }, []);

  const fetchPayments = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (eventFilter) params.event_id = eventFilter;
      if (clientFilter) params.user_id = clientFilter;
      const result = await getPayments(params);
      setPayments(result.items ?? result);
    } catch (err) {
      setError(err?.message || RU.messages.paymentsLoadError);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, eventFilter, clientFilter]);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  useEffect(() => {
    if (searchParams.get("create") !== "1") return;

    if (canManagePayments) {
      setModalError("");
      setIsCreateModalOpen(true);
      if (!modalEventsLoaded && modalEvents.length === 0) {
        loadModalEvents();
      }
    }

    const next = new URLSearchParams(searchParams);
    next.delete("create");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, canManagePayments, modalEventsLoaded, modalEvents.length, loadModalEvents]);

  const filteredPayments = useMemo(() => {
    if (!search.trim()) return payments;
    const term = search.trim().toLowerCase();
    return payments.filter((p) => {
      return (
        String(p.client_name || "").toLowerCase().includes(term) ||
        String(p.event_title || "").toLowerCase().includes(term) ||
        String(p.source || "").toLowerCase().includes(term)
      );
    });
  }, [payments, search]);

  const resetCreateForm = useCallback(() => {
    setCreateMode("existing");
    setExistingLookupField("telegram");
    setExistingLookupValue("");
    setExistingMatches([]);
    setSelectedExistingClientId("");
    setNewName("");
    setNewPhone("");
    setNewTelegram("");
    setCreateEventId("");
    setCreateAmount("");
    setModalError("");
  }, []);

  const closeCreateModal = useCallback(() => {
    setIsCreateModalOpen(false);
    setSubmitting(false);
    resetCreateForm();
  }, [resetCreateForm]);

  const handleFindExistingClient = useCallback(async () => {
    const needle = normalizeLookup(existingLookupField, existingLookupValue);
    if (!needle) {
      setExistingMatches([]);
      setSelectedExistingClientId("");
      setModalError(UI_TEXT.lookupRequired);
      return;
    }
    setModalError("");
    const result = await getClients({ limit: 50, offset: 0, search: needle });
    const items = result?.items ?? result ?? [];
    const matches = items.filter((item) => matchesStrict(existingLookupField, item, needle));
    setExistingMatches(matches);
    if (matches.length === 0) {
      setSelectedExistingClientId("");
      setModalError(UI_TEXT.clientNotFound);
      return;
    }
    if (matches.length === 1) {
      setSelectedExistingClientId(String(matches[0].id));
      return;
    }
    setSelectedExistingClientId("");
  }, [existingLookupField, existingLookupValue]);

  const handleExistingLookupFieldChange = useCallback((event) => {
    setExistingLookupField(event.target.value);
    setExistingMatches([]);
    setSelectedExistingClientId("");
    setModalError("");
  }, []);

  const handleExistingLookupValueChange = useCallback((event) => {
    setExistingLookupValue(event.target.value);
    setExistingMatches([]);
    setSelectedExistingClientId("");
    setModalError("");
  }, []);

  const handleSubmitCreatePayment = async (event) => {
    event.preventDefault();
    if (!canManagePayments) return;

    const amountText = String(createAmount || "").trim();
    if (!/^\d+$/.test(amountText) || Number(amountText) <= 0) {
      setModalError(UI_TEXT.amountInvalid);
      return;
    }

    try {
      setSubmitting(true);
      setModalError("");

      let client;
      if (createMode === "existing") {
        if (existingMatches.length === 0) {
          setModalError(UI_TEXT.findClientFirst);
          return;
        }
        if (existingMatches.length > 1 && !selectedExistingClientId) {
          setModalError(UI_TEXT.chooseClientFromList);
          return;
        }
        client =
          existingMatches.length === 1
            ? existingMatches[0]
            : existingMatches.find(
                (item) => String(item.id) === String(selectedExistingClientId),
              );
        if (!client) {
          setModalError(UI_TEXT.chooseClientFromList);
          return;
        }
      } else {
        const trimmedName = String(newName || "").trim();
        if (!trimmedName) {
          setModalError(UI_TEXT.nameRequired);
          return;
        }
        client = await createClient({
          name: trimmedName,
          phone: String(newPhone || "").trim() || null,
          telegram: String(newTelegram || "").trim() || null,
        });
      }

      const created = await createPayment({
        user_id: client.id,
        event_id: createEventId ? Number(createEventId) : null,
        amount: Number(amountText),
        currency: "RUB",
        source: UI_TEXT.cashSource,
      });
      const paid =
        created?.status === "paid"
          ? created
          : await updatePayment(created.id, { status: "paid" });

      setPayments((prev) => [paid, ...prev.filter((item) => item.id !== paid.id)]);
      closeCreateModal();
    } catch (err) {
      setModalError(err?.message || RU.messages.paymentUpdateError);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateStatus = async (paymentId, status) => {
    try {
      const updated = await updatePayment(paymentId, { status });
      setPayments((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    } catch (err) {
      setError(err?.message || RU.messages.paymentUpdateError);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{RU.labels.paymentsTitle}</h2>
            <p className="text-sm text-slate-500">{RU.labels.paymentsSubtitle}</p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 xl:w-auto xl:flex-nowrap xl:justify-end">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={RU.labels.paymentSearch}
              className="w-full min-w-[260px] xl:w-[340px] 2xl:w-[420px]"
            />
            <select
              className="h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">{RU.labels.allStatuses}</option>
              <option value="pending">{RU.statuses.pending}</option>
              <option value="paid">{RU.statuses.paid}</option>
              <option value="failed">{RU.statuses.failed}</option>
              <option value="cancelled">{RU.statuses.cancelled}</option>
            </select>
            <select
              className="h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700"
              value={eventFilter}
              onChange={(e) => setEventFilter(e.target.value)}
            >
              <option value="">{RU.labels.allEvents}</option>
              {events.map((eventItem) => (
                <option key={eventItem.id} value={eventItem.id}>
                  {eventItem.title}
                </option>
              ))}
            </select>
            <select
              className="h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700"
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
            >
              <option value="">{RU.labels.allClients}</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <SkeletonCard key={i} rows={2} className="p-4" />
              ))}
            </div>
          ) : filteredPayments.length ? (
            <Table>
              <THead>
                <TR>
                  <TH>{RU.labels.client}</TH>
                  <TH>{RU.nav.events}</TH>
                  <TH>{RU.labels.amount}</TH>
                  <TH>{RU.labels.status}</TH>
                  <TH>{RU.labels.source}</TH>
                  <TH>{RU.labels.createdAt}</TH>
                  <TH className="w-[1%] whitespace-nowrap">{RU.labels.actions}</TH>
                </TR>
              </THead>
              <TBody>
                {filteredPayments.map((payment) => (
                  <TR key={payment.id}>
                    <TD>
                      <div className="font-medium text-slate-900">
                        {payment.client_name || RU.messages.emDash}
                      </div>
                      <div className="text-xs text-slate-500">
                        {payment.tg_id ? `tg_id ${payment.tg_id}` : ""}
                      </div>
                    </TD>
                    <TD>{payment.event_title || RU.labels.noEvent}</TD>
                    <TD className="font-semibold">{formatCurrencyRub(payment.amount)}</TD>
                    <TD>
                      <Badge variant={statusVariant(payment.status)}>
                        {statusLabel(payment.status)}
                      </Badge>
                    </TD>
                    <TD>{payment.source || RU.messages.emDash}</TD>
                    <TD>
                      {formatDateRu(payment.created_at, {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </TD>
                    <TD>
                      <div className="flex flex-nowrap gap-1.5">
                        <Button
                          variant="secondary"
                          className="h-8 whitespace-nowrap px-2.5 text-xs"
                          onClick={() => handleUpdateStatus(payment.id, "paid")}
                          disabled={!canManagePayments}
                        >
                          {RU.buttons.markPaid}
                        </Button>
                        <Button
                          variant="secondary"
                          className="h-8 whitespace-nowrap px-2.5 text-xs"
                          onClick={() => handleUpdateStatus(payment.id, "failed")}
                          disabled={!canManagePayments}
                        >
                          {RU.buttons.markFailed}
                        </Button>
                        <Button
                          variant="secondary"
                          className="h-8 whitespace-nowrap px-2.5 text-xs"
                          onClick={() => handleUpdateStatus(payment.id, "cancelled")}
                          disabled={!canManagePayments}
                        >
                          {RU.buttons.markCancelled}
                        </Button>
                      </div>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState title={RU.labels.noPayments} description={RU.labels.noPaymentsHint} />
          )}
        </CardContent>
      </Card>

      {isCreateModalOpen && canManagePayments && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-2xl rounded-2xl bg-white shadow-xl">
            <form onSubmit={handleSubmitCreatePayment} className="space-y-4 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">{UI_TEXT.createTitle}</h3>
                  <p className="text-sm text-slate-500">{UI_TEXT.createSubtitle}</p>
                </div>
                <Button type="button" variant="ghost" onClick={closeCreateModal}>
                  {UI_TEXT.cancel}
                </Button>
              </div>

              {modalError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
                  {modalError}
                </div>
              )}

              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700">{UI_TEXT.clientExists}</p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={`h-10 rounded-xl border px-4 text-sm ${
                      createMode === "existing"
                        ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                        : "border-slate-300 bg-white text-slate-700"
                    }`}
                    onClick={() => setCreateMode("existing")}
                  >
                    {UI_TEXT.yes}
                  </button>
                  <button
                    type="button"
                    className={`h-10 rounded-xl border px-4 text-sm ${
                      createMode === "new"
                        ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                        : "border-slate-300 bg-white text-slate-700"
                    }`}
                    onClick={() => setCreateMode("new")}
                  >
                    {UI_TEXT.no}
                  </button>
                </div>
              </div>

              {createMode === "existing" ? (
                <div className="space-y-3">
                  <div className="grid gap-3 md:grid-cols-[220px_1fr_auto]">
                    <div className="space-y-1.5">
                      <label className="text-sm text-slate-700">{UI_TEXT.lookupBy}</label>
                      <select
                        className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700"
                        value={existingLookupField}
                        onChange={handleExistingLookupFieldChange}
                        disabled={submitting}
                      >
                        <option value="telegram">{UI_TEXT.lookupTelegram}</option>
                        <option value="phone">{UI_TEXT.lookupPhone}</option>
                        <option value="email">{UI_TEXT.lookupEmail}</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm text-slate-700">{UI_TEXT.lookupValue}</label>
                      <Input
                        value={existingLookupValue}
                        onChange={handleExistingLookupValueChange}
                        placeholder={
                          existingLookupField === "phone"
                            ? UI_TEXT.lookupPhonePlaceholder
                            : existingLookupField === "email"
                              ? UI_TEXT.lookupEmailPlaceholder
                              : UI_TEXT.lookupTelegramPlaceholder
                        }
                        disabled={submitting}
                        onKeyDown={(event) => {
                          if (event.key !== "Enter") return;
                          event.preventDefault();
                          if (submitting) return;
                          handleFindExistingClient();
                        }}
                      />
                    </div>
                    <div className="flex items-end">
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={handleFindExistingClient}
                        disabled={submitting}
                      >
                        {UI_TEXT.find}
                      </Button>
                    </div>
                  </div>
                  {existingMatches.length > 1 && (
                    <div className="space-y-1.5">
                      <label className="text-sm text-slate-700">{UI_TEXT.chooseClient}</label>
                      <select
                        className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700"
                        value={selectedExistingClientId}
                        onChange={(event) => {
                          setSelectedExistingClientId(event.target.value);
                          setModalError("");
                        }}
                        disabled={submitting}
                      >
                        <option value="">{UI_TEXT.chooseClient}</option>
                        {existingMatches.map((item) => (
                          <option key={item.id} value={String(item.id)}>
                            {formatExistingClientOption(item)}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1.5 md:col-span-2">
                    <label className="text-sm text-slate-700">{UI_TEXT.name}</label>
                    <Input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder={UI_TEXT.namePlaceholder}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm text-slate-700">{UI_TEXT.phoneOptional}</label>
                    <Input
                      value={newPhone}
                      onChange={(e) => setNewPhone(e.target.value)}
                      placeholder="+7..."
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm text-slate-700">{UI_TEXT.telegramOptional}</label>
                    <Input
                      value={newTelegram}
                      onChange={(e) => setNewTelegram(e.target.value)}
                      placeholder="@nickname"
                    />
                  </div>
                </div>
              )}

              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1.5">
                  <label className="text-sm text-slate-700">{UI_TEXT.event}</label>
                  <select
                    className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700"
                    value={createEventId}
                    onChange={(e) => setCreateEventId(e.target.value)}
                  >
                    <option value="">{UI_TEXT.noEvent}</option>
                    {modalEvents.map((eventItem) => (
                      <option key={eventItem.id} value={String(eventItem.id)}>
                        {eventItem.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm text-slate-700">{UI_TEXT.amount}</label>
                  <Input
                    type="number"
                    min="1"
                    step="1"
                    value={createAmount}
                    onChange={(e) => setCreateAmount(e.target.value)}
                    placeholder="5000"
                  />
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <div>{UI_TEXT.paidStatus}</div>
                <div>{UI_TEXT.sourceLine}</div>
                <div>{UI_TEXT.dateLine}</div>
              </div>

              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={closeCreateModal}>
                  {UI_TEXT.cancel}
                </Button>
                <Button
                  type="submit"
                  disabled={submitting || !/^\d+$/.test(String(createAmount || "").trim())}
                >
                  {submitting ? RU.messages.loading : UI_TEXT.create}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
