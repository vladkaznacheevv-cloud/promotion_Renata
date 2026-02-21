/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useState } from "react";

import { RU, stageLabel } from "../i18n/ru";
import Button from "./ui/Button";
import Input from "./ui/Input";
import Modal from "./ui/Modal";

const STATUS_OPTIONS = ["Новый", "В работе", "Клиент", "VIP Клиент"];
const STAGE_OPTIONS = [
  "NEW",
  "ENGAGED",
  "READY_TO_PAY",
  "MANAGER_FOLLOWUP",
  "PAID",
  "INACTIVE",
];

export default function ClientModal({ open, onClose, onSubmit, initialData, error, role = "viewer" }) {
  const canManage = role === "admin" || role === "manager";

  const [name, setName] = useState("");
  const [telegram, setTelegram] = useState("");
  const [status, setStatus] = useState("Новый");
  const [stage, setStage] = useState("NEW");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [tgId, setTgId] = useState("");

  useEffect(() => {
    if (initialData) {
      setName(initialData.name || "");
      setTelegram(initialData.telegram || "");
      setStatus(initialData.status || "Новый");
      setStage(initialData.stage || "NEW");
      setPhone(initialData.phone || "");
      setEmail(initialData.email || "");
      setTgId("");
    } else {
      setName("");
      setTelegram("");
      setStatus("Новый");
      setStage("NEW");
      setPhone("");
      setEmail("");
      setTgId("");
    }
  }, [initialData, open]);

  const handleSubmit = (event) => {
    event.preventDefault();
    const payload = {
      name: name.trim(),
      telegram: telegram.trim() || null,
      phone: phone.trim() || null,
      email: email.trim().toLowerCase() || null,
      status,
      stage,
      tg_id: tgId ? Number(tgId) : undefined,
    };
    onSubmit(payload);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={initialData ? `${RU.buttons.edit} ${RU.labels.client.toLowerCase()}` : RU.buttons.addClient}
      footer={
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} type="button">
            {RU.buttons.cancel}
          </Button>
          <Button type="submit" form="client-form">
            {RU.buttons.save}
          </Button>
        </div>
      }
    >
      <form id="client-form" className="space-y-4" onSubmit={handleSubmit}>
        {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.client}
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          Telegram @имя
          <Input value={telegram} onChange={(e) => setTelegram(e.target.value)} placeholder="@username" />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          Telegram ID
          <Input type="number" value={tgId} onChange={(e) => setTgId(e.target.value)} placeholder="10001" />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.phone}
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+79991234567" />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.email}
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.status}
          <select
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {STATUS_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.stage}
          <select
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            value={stage}
            onChange={(e) => setStage(e.target.value)}
            disabled={!canManage}
          >
            {STAGE_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {stageLabel(value)}
              </option>
            ))}
          </select>
        </label>
      </form>
    </Modal>
  );
}
