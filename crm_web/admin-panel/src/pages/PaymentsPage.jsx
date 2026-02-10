import { useCallback, useEffect, useMemo, useState } from "react";

import { getPayments, updatePayment } from "../api/payments";
import { useAuth } from "../auth/AuthContext";
import { RU, formatCurrencyRub, formatDateRu } from "../i18n/ru";
import EmptyState from "../components/EmptyState";
import SkeletonCard from "../components/SkeletonCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import Input from "../components/ui/Input";
import { Table, THead, TBody, TR, TH, TD } from "../components/ui/Table";

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

export default function PaymentsPage({ clients = [], events = [], role }) {
  const auth = useAuth();
  const effectiveRole = role || auth.currentUser?.role || "viewer";

  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [statusFilter, setStatusFilter] = useState("");
  const [eventFilter, setEventFilter] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  const [search, setSearch] = useState("");

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

  const canManagePayments = effectiveRole === "admin";

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
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{RU.labels.paymentsTitle}</h2>
            <p className="text-sm text-slate-500">{RU.labels.paymentsSubtitle}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={RU.labels.paymentSearch}
              className="min-w-[220px]"
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
              {events.map((event) => (
                <option key={event.id} value={event.id}>{event.title}</option>
              ))}
            </select>
            <select
              className="h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700"
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
            >
              <option value="">{RU.labels.allClients}</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>{client.name}</option>
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
                  <TH>{RU.labels.actions}</TH>
                </TR>
              </THead>
              <TBody>
                {filteredPayments.map((payment) => (
                  <TR key={payment.id}>
                    <TD>
                      <div className="font-medium text-slate-900">{payment.client_name || RU.messages.emDash}</div>
                      <div className="text-xs text-slate-500">{payment.tg_id ? `tg_id ${payment.tg_id}` : ""}</div>
                    </TD>
                    <TD>{payment.event_title || RU.labels.noEvent}</TD>
                    <TD className="font-semibold">{formatCurrencyRub(payment.amount)}</TD>
                    <TD>
                      <Badge variant={statusVariant(payment.status)}>{statusLabel(payment.status)}</Badge>
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
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="secondary"
                          className="text-xs"
                          onClick={() => handleUpdateStatus(payment.id, "paid")}
                          disabled={!canManagePayments}
                        >
                          {RU.buttons.markPaid}
                        </Button>
                        <Button
                          variant="secondary"
                          className="text-xs"
                          onClick={() => handleUpdateStatus(payment.id, "failed")}
                          disabled={!canManagePayments}
                        >
                          {RU.buttons.markFailed}
                        </Button>
                        <Button
                          variant="secondary"
                          className="text-xs"
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
    </div>
  );
}


