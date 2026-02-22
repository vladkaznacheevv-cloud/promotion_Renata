/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from "react";

import { RU } from "../i18n/ru";
import Button from "./ui/Button";
import Input from "./ui/Input";
import Modal from "./ui/Modal";

const DEFAULT_HOSTS = `Диана Даниелян — клинический психолог, гештальттерапевт
Елена Анищенко — клинический психолог, супервизор, гештальттерапевт`;
const DEFAULT_DURATION_HINT = "Длительность игры 1–4 часа, в зависимости от количества игроков.";
const DEFAULT_BOOKING_HINT = "Запись по запросу в удобное время и дату.";

const WEEKDAY_OPTIONS = [
  { value: "MO", label: "Понедельник" },
  { value: "TU", label: "Вторник" },
  { value: "WE", label: "Среда" },
  { value: "TH", label: "Четверг" },
  { value: "FR", label: "Пятница" },
  { value: "SA", label: "Суббота" },
  { value: "SU", label: "Воскресенье" },
];

const weekdayLabel = (code) => WEEKDAY_OPTIONS.find((item) => item.value === code)?.label?.toLowerCase() || "вторник";

const formatRecurringPreview = (values) => {
  const positions = [...(values.recurring_positions || [])]
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value >= 1 && value <= 5)
    .sort((a, b) => a - b);
  const posText = positions.length ? positions.map((pos) => `${pos}-й`).join(" и ") : "2-й и 4-й";
  const from = values.start_time || "17:00";
  const to = values.end_time || "21:00";
  return `${posText} ${weekdayLabel(values.recurring_weekday)}, ${from}–${to}`;
};

function validate(values) {
  const errors = {};

  if (!values.title.trim()) {
    errors.title = "Укажите название мероприятия.";
  }
  if (!values.description.trim()) {
    errors.description = "Добавьте описание мероприятия.";
  }
  if (values.schedule_type === "one_time" && !values.date) {
    errors.date = "Укажите дату мероприятия.";
  }
  if (values.schedule_type === "recurring" && !(values.recurring_positions || []).length) {
    errors.recurring_positions = "Выберите хотя бы одну позицию в месяце.";
  }

  return errors;
}

const parseRecurringRule = (rule) => {
  if (!rule || typeof rule !== "object") {
    return { byweekday: "TU", bysetpos: [2, 4] };
  }
  const weekday = String(rule.byweekday || "TU").toUpperCase();
  const bysetpos = Array.isArray(rule.bysetpos)
    ? rule.bysetpos.map((item) => Number(item)).filter((item) => Number.isInteger(item) && item >= 1 && item <= 5)
    : [2, 4];
  return {
    byweekday: weekday,
    bysetpos: bysetpos.length ? bysetpos : [2, 4],
  };
};

export default function EventFormModal({
  open,
  onClose,
  onSubmit,
  initialData,
  error,
  submitting = false,
}) {
  const [values, setValues] = useState({
    title: "",
    description: "",
    date: "",
    location: "",
    price: "",
    status: "active",
    link_getcourse: "",
    schedule_type: "one_time",
    recurring_weekday: "TU",
    recurring_positions: [2, 4],
    start_time: "17:00",
    end_time: "21:00",
    hosts: DEFAULT_HOSTS,
    price_individual_rub: "8000",
    price_group_rub: "5000",
    duration_hint: DEFAULT_DURATION_HINT,
    booking_hint: DEFAULT_BOOKING_HINT,
  });
  const [touched, setTouched] = useState({});

  useEffect(() => {
    if (initialData) {
      const recurring = parseRecurringRule(initialData.recurring_rule);
      setValues({
        title: initialData.title || "",
        description: initialData.description || "",
        date: initialData.date || "",
        location: initialData.location || "",
        price: initialData.price ?? "",
        status: initialData.status || "active",
        link_getcourse: initialData.link_getcourse || "",
        schedule_type: initialData.schedule_type || (initialData.date ? "one_time" : "rolling"),
        recurring_weekday: recurring.byweekday,
        recurring_positions: recurring.bysetpos,
        start_time: initialData.start_time || "17:00",
        end_time: initialData.end_time || "21:00",
        hosts: initialData.hosts || DEFAULT_HOSTS,
        price_individual_rub: initialData.price_individual_rub ?? "8000",
        price_group_rub: initialData.price_group_rub ?? "5000",
        duration_hint: initialData.duration_hint || DEFAULT_DURATION_HINT,
        booking_hint: initialData.booking_hint || DEFAULT_BOOKING_HINT,
      });
    } else {
      setValues({
        title: "",
        description: "",
        date: "",
        location: "",
        price: "",
        status: "active",
        link_getcourse: "",
        schedule_type: "one_time",
        recurring_weekday: "TU",
        recurring_positions: [2, 4],
        start_time: "17:00",
        end_time: "21:00",
        hosts: DEFAULT_HOSTS,
        price_individual_rub: "8000",
        price_group_rub: "5000",
        duration_hint: DEFAULT_DURATION_HINT,
        booking_hint: DEFAULT_BOOKING_HINT,
      });
    }
    setTouched({});
  }, [initialData, open]);

  const errors = useMemo(() => validate(values), [values]);
  const hasErrors = Object.keys(errors).length > 0;
  const isRecurring = values.schedule_type === "recurring";
  const isRolling = values.schedule_type === "rolling";
  const recurringPreview = useMemo(() => formatRecurringPreview(values), [values]);

  const onFieldChange = (field, value) => {
    setValues((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "schedule_type" && value === "rolling") {
        next.date = "";
        next.status = "active";
      }
      if (field === "schedule_type" && value === "recurring") {
        if (!next.recurring_positions?.length) next.recurring_positions = [2, 4];
        if (!next.recurring_weekday) next.recurring_weekday = "TU";
        if (!next.start_time) next.start_time = "17:00";
        if (!next.end_time) next.end_time = "21:00";
      }
      return next;
    });
  };

  const toggleRecurringPosition = (position) => {
    setValues((prev) => {
      const exists = prev.recurring_positions.includes(position);
      const nextPositions = exists
        ? prev.recurring_positions.filter((value) => value !== position)
        : [...prev.recurring_positions, position];
      return { ...prev, recurring_positions: nextPositions.sort((a, b) => a - b) };
    });
  };

  const applyRecurringPreset = () => {
    setValues((prev) => ({
      ...prev,
      schedule_type: "recurring",
      recurring_weekday: "TU",
      recurring_positions: [2, 4],
      start_time: "17:00",
      end_time: "21:00",
    }));
  };

  const onFieldBlur = (field) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setTouched({
      title: true,
      description: true,
      date: values.schedule_type === "one_time",
      recurring_positions: values.schedule_type === "recurring",
    });

    if (hasErrors || submitting) {
      return;
    }

    const payload = {
      title: values.title.trim(),
      description: values.description.trim(),
      date: values.schedule_type === "rolling" ? null : (values.date || null),
      location: values.location.trim() || null,
      price: values.price === "" ? null : Number(values.price),
      status: values.status,
      link_getcourse: values.link_getcourse.trim() || null,
      schedule_type: values.schedule_type,
      start_time: isRecurring ? (values.start_time || null) : null,
      end_time: isRecurring ? (values.end_time || null) : null,
      recurring_rule: isRecurring
        ? {
            freq: "MONTHLY",
            byweekday: values.recurring_weekday || "TU",
            bysetpos: [...values.recurring_positions].sort((a, b) => a - b),
          }
        : null,
      hosts: values.hosts.trim() || null,
      price_individual_rub: values.price_individual_rub === "" ? null : Number(values.price_individual_rub),
      price_group_rub: values.price_group_rub === "" ? null : Number(values.price_group_rub),
      duration_hint: values.duration_hint.trim() || null,
      booking_hint: values.booking_hint.trim() || null,
    };

    await onSubmit(payload);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={initialData ? `${RU.buttons.edit} ${RU.nav.events.toLowerCase()}` : RU.buttons.createEvent}
      footer={
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} type="button" disabled={submitting}>
            {RU.buttons.cancel}
          </Button>
          <Button type="submit" form="event-form" disabled={hasErrors || submitting}>
            {submitting ? "Сохранение..." : RU.buttons.save}
          </Button>
        </div>
      }
    >
      <form id="event-form" className="space-y-4" onSubmit={handleSubmit}>
        {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.scheduleType}
          <select
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            value={values.schedule_type}
            onChange={(e) => onFieldChange("schedule_type", e.target.value)}
          >
            <option value="one_time">{RU.labels.scheduleTypeOneTime}</option>
            <option value="recurring">{RU.labels.scheduleTypeRecurring}</option>
            <option value="rolling">{RU.labels.scheduleTypeRolling}</option>
          </select>
        </label>

        {isRecurring && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-700">{RU.labels.schedulePreview}</p>
              <Button variant="secondary" type="button" onClick={applyRecurringPreset}>
                {RU.labels.recurringPresetTwiceMonth}
              </Button>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">
                {RU.labels.recurringWeekday}
                <select
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
                  value={values.recurring_weekday}
                  onChange={(e) => onFieldChange("recurring_weekday", e.target.value)}
                >
                  {WEEKDAY_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>

              <div className="text-sm font-medium text-slate-700">
                {RU.labels.recurringPositions}
                <div className="mt-1 flex flex-wrap gap-2">
                  {[1, 2, 3, 4, 5].map((position) => (
                    <label
                      key={position}
                      className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                    >
                      <input
                        type="checkbox"
                        checked={values.recurring_positions.includes(position)}
                        onChange={() => toggleRecurringPosition(position)}
                      />
                      {position}
                    </label>
                  ))}
                </div>
                {touched.recurring_positions && errors.recurring_positions && (
                  <p className="mt-1 text-xs text-red-600">{errors.recurring_positions}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">
                {RU.labels.recurringTimeFrom}
                <Input type="time" value={values.start_time} onChange={(e) => onFieldChange("start_time", e.target.value)} />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                {RU.labels.recurringTimeTo}
                <Input type="time" value={values.end_time} onChange={(e) => onFieldChange("end_time", e.target.value)} />
              </label>
            </div>

            <div className="rounded-lg border border-indigo-100 bg-white p-3 text-sm text-slate-700">
              <div className="text-xs uppercase tracking-wide text-slate-500">{RU.labels.recurringPreview}</div>
              <div className="mt-1 font-medium text-slate-900">{recurringPreview}</div>
            </div>
          </div>
        )}

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.name} *
          <Input
            value={values.title}
            onChange={(e) => onFieldChange("title", e.target.value)}
            onBlur={() => onFieldBlur("title")}
            required
          />
          {touched.title && errors.title && <p className="mt-1 text-xs text-red-600">{errors.title}</p>}
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.eventDescription} *
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            value={values.description}
            onChange={(e) => onFieldChange("description", e.target.value)}
            onBlur={() => onFieldBlur("description")}
            rows={4}
            required
          />
          {touched.description && errors.description && (
            <p className="mt-1 text-xs text-red-600">{errors.description}</p>
          )}
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.date}{values.schedule_type === "one_time" ? " *" : ""}
          <Input
            type="date"
            value={values.date}
            onChange={(e) => onFieldChange("date", e.target.value)}
            onBlur={() => onFieldBlur("date")}
            required={values.schedule_type === "one_time"}
            disabled={isRolling}
          />
          {touched.date && errors.date && <p className="mt-1 text-xs text-red-600">{errors.date}</p>}
          {isRolling && (
            <p className="mt-1 text-xs text-slate-500">{RU.messages.rollingBookingHintDefault}</p>
          )}
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.location}
          <Input value={values.location} onChange={(e) => onFieldChange("location", e.target.value)} />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.eventHosts}
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            value={values.hosts}
            onChange={(e) => onFieldChange("hosts", e.target.value)}
            rows={3}
          />
        </label>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="block text-sm font-medium text-slate-700">
            {RU.labels.priceIndividual} (₽)
            <Input
              type="number"
              min="0"
              step="1"
              value={values.price_individual_rub}
              onChange={(e) => onFieldChange("price_individual_rub", e.target.value)}
            />
            <p className="mt-1 text-xs font-normal text-slate-500">{RU.labels.priceIndividualHint}</p>
          </label>

          <label className="block text-sm font-medium text-slate-700">
            {RU.labels.priceGroup} (₽)
            <Input
              type="number"
              min="0"
              step="1"
              value={values.price_group_rub}
              onChange={(e) => onFieldChange("price_group_rub", e.target.value)}
            />
            <p className="mt-1 text-xs font-normal text-slate-500">{RU.labels.priceGroupHint}</p>
          </label>
        </div>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.price} (₽)
          <Input
            type="number"
            value={values.price}
            onChange={(e) => onFieldChange("price", e.target.value)}
            min="0"
            step="0.01"
          />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.durationHint}
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            value={values.duration_hint}
            onChange={(e) => onFieldChange("duration_hint", e.target.value)}
            rows={2}
          />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.bookingHint}
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            value={values.booking_hint}
            onChange={(e) => onFieldChange("booking_hint", e.target.value)}
            rows={2}
          />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.status}
          <select
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            value={values.status}
            onChange={(e) => onFieldChange("status", e.target.value)}
          >
            <option value="active">{RU.statuses.active}</option>
            <option value="finished">{RU.statuses.finished}</option>
          </select>
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.eventGetCourseLink}
          <Input
            value={values.link_getcourse}
            onChange={(e) => onFieldChange("link_getcourse", e.target.value)}
            placeholder="https://..."
          />
        </label>
      </form>
    </Modal>
  );
}
