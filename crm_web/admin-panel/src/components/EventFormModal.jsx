/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from "react";

import { RU } from "../i18n/ru";
import Button from "./ui/Button";
import Input from "./ui/Input";
import Modal from "./ui/Modal";

const WEEKDAY_OPTIONS = [
  { value: "MO", label: "Понедельник" },
  { value: "TU", label: "Вторник" },
  { value: "WE", label: "Среда" },
  { value: "TH", label: "Четверг" },
  { value: "FR", label: "Пятница" },
  { value: "SA", label: "Суббота" },
  { value: "SU", label: "Воскресенье" },
];

const EMPTY_PRICE_OPTION = { label: "", price_rub: "", note: "" };

function trimOrNull(value) {
  const text = String(value ?? "").trim();
  return text || null;
}

function buildDefaultPricingOptions() {
  return [
    { label: RU.labels.priceIndividualDisplay || "Индивидуально", price_rub: "8000", note: "" },
    { label: RU.labels.priceGroupDisplay || "Группа", price_rub: "5000", note: "за участника" },
  ];
}

function normalizeOccurrenceDates(values) {
  if (!Array.isArray(values)) return [""];
  const clean = values
    .map((value) => String(value || "").slice(0, 10))
    .filter((value, index, arr) => arr.indexOf(value) === index);
  return clean.length ? clean : [""];
}

function normalizePricingRows(value, fallbackPrice) {
  if (Array.isArray(value) && value.length) {
    const rows = value.map((item) => ({
      label: String(item?.label || ""),
      price_rub: item?.price_rub != null ? String(item.price_rub) : "",
      note: String(item?.note || ""),
    }));
    return rows.length ? rows : [EMPTY_PRICE_OPTION];
  }
  if (fallbackPrice != null && fallbackPrice !== "") {
    return [{ label: RU.labels.price || "Цена", price_rub: String(fallbackPrice), note: "" }];
  }
  return buildDefaultPricingOptions();
}

function parseRecurringRule(rule) {
  if (!rule || typeof rule !== "object") {
    return { byweekday: "TU", bysetpos: [2, 4] };
  }
  const weekday = String(rule.byweekday || "TU").toUpperCase();
  const positions = Array.isArray(rule.bysetpos)
    ? rule.bysetpos
        .map((item) => Number(item))
        .filter((item) => Number.isInteger(item) && item >= 1 && item <= 5)
    : [2, 4];
  return {
    byweekday: weekday,
    bysetpos: positions.length ? [...new Set(positions)].sort((a, b) => a - b) : [2, 4],
  };
}

function weekdayLabel(code) {
  return WEEKDAY_OPTIONS.find((item) => item.value === code)?.label?.toLowerCase() || "вторник";
}

function formatRecurringPreview(values) {
  const from = values.start_time || "17:00";
  const to = values.end_time || "21:00";
  if (values.recurring_mode === "dates") {
    const dates = (values.occurrence_dates || []).filter(Boolean);
    if (!dates.length) return RU.messages.notSet;
    const text = dates
      .map((value) => {
        const [yyyy, mm, dd] = String(value).slice(0, 10).split("-");
        if (!dd || !mm) return value;
        return `${dd}.${mm}`;
      })
      .join(", ");
    return `Даты: ${text}; ${from}-${to}`;
  }

  const positions = [...(values.recurring_positions || [])]
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value >= 1 && value <= 5)
    .sort((a, b) => a - b);
  const posText = positions.length ? positions.map((pos) => `${pos}-й`).join(" и ") : "2-й и 4-й";
  const startDate = values.start_date ? `Старт ${values.start_date.split("-").reverse().join(".")}; ` : "";
  return `${startDate}${posText} ${weekdayLabel(values.recurring_weekday)}, ${from}-${to}`;
}

function validate(values) {
  const errors = {};

  if (!String(values.title || "").trim()) {
    errors.title = "Укажите название мероприятия.";
  }
  if (!String(values.description || "").trim()) {
    errors.description = "Добавьте описание мероприятия.";
  }
  if (values.schedule_type === "one_time" && !values.date) {
    errors.date = "Укажите дату мероприятия.";
  }
  if (values.schedule_type === "recurring") {
    if (!values.start_date) {
      errors.start_date = "Укажите дату старта.";
    }
    if (values.recurring_mode === "rule") {
      if (!(values.recurring_positions || []).length) {
        errors.recurring_positions = "Выберите хотя бы одну позицию в месяце.";
      }
    } else {
      const dates = (values.occurrence_dates || []).filter(Boolean);
      if (!dates.length) {
        errors.occurrence_dates = "Добавьте хотя бы одну дату.";
      }
    }
  }

  const validPrices = (values.pricing_options || []).filter((row) => {
    const label = String(row?.label || "").trim();
    const priceNum = Number(row?.price_rub);
    return label && Number.isFinite(priceNum) && priceNum >= 0;
  });
  if (!validPrices.length) {
    errors.pricing_options = "Добавьте хотя бы один вариант цены (название и сумма).";
  }

  return errors;
}

function buildInitialValues(initialData) {
  const recurring = parseRecurringRule(initialData?.recurring_rule);
  const occurrenceDates = normalizeOccurrenceDates(initialData?.occurrence_dates || []);
  const hasOccurrenceDates = Boolean((initialData?.occurrence_dates || []).length);
  return {
    title: initialData?.title || "",
    description: initialData?.description || "",
    date: initialData?.date || "",
    location: initialData?.location || "",
    status: initialData?.status || "active",
    schedule_type: initialData?.schedule_type || (initialData?.date ? "one_time" : "rolling"),
    start_date: initialData?.start_date ? String(initialData.start_date).slice(0, 10) : "",
    recurring_mode: hasOccurrenceDates ? "dates" : "rule",
    recurring_weekday: recurring.byweekday,
    recurring_positions: recurring.bysetpos,
    occurrence_dates: occurrenceDates,
    start_time: initialData?.start_time || "17:00",
    end_time: initialData?.end_time || "21:00",
    hosts: initialData?.hosts || "",
    pricing_options: normalizePricingRows(initialData?.pricing_options, initialData?.price),
    duration_hint: initialData?.duration_hint || "",
    booking_hint: initialData?.booking_hint || RU.messages.rollingBookingHintDefault,
  };
}

export default function EventFormModal({
  open,
  onClose,
  onSubmit,
  initialData,
  error,
  submitting = false,
}) {
  const [values, setValues] = useState(buildInitialValues(null));
  const [touched, setTouched] = useState({});

  useEffect(() => {
    setValues(buildInitialValues(initialData || null));
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
      if (field === "schedule_type") {
        if (value === "rolling") {
          next.date = "";
          next.start_date = "";
          next.occurrence_dates = [""];
        }
        if (value === "recurring") {
          next.date = "";
          if (!next.start_date) next.start_date = "";
          if (!next.start_time) next.start_time = "17:00";
          if (!next.end_time) next.end_time = "21:00";
          if (!next.recurring_positions?.length) next.recurring_positions = [2, 4];
          if (!next.recurring_weekday) next.recurring_weekday = "TU";
          if (!next.recurring_mode) next.recurring_mode = "rule";
          if (!Array.isArray(next.occurrence_dates) || !next.occurrence_dates.length) {
            next.occurrence_dates = [""];
          }
        }
      }
      if (field === "recurring_mode" && value === "dates") {
        if (!Array.isArray(next.occurrence_dates) || !next.occurrence_dates.length) {
          next.occurrence_dates = [""];
        }
      }
      return next;
    });
  };

  const onFieldBlur = (field) => setTouched((prev) => ({ ...prev, [field]: true }));

  const toggleRecurringPosition = (position) => {
    setValues((prev) => {
      const exists = prev.recurring_positions.includes(position);
      const recurring_positions = exists
        ? prev.recurring_positions.filter((value) => value !== position)
        : [...prev.recurring_positions, position];
      return { ...prev, recurring_positions: recurring_positions.sort((a, b) => a - b) };
    });
  };

  const applyRecurringPreset = () => {
    setValues((prev) => ({
      ...prev,
      schedule_type: "recurring",
      recurring_mode: "rule",
      recurring_weekday: "TU",
      recurring_positions: [2, 4],
      start_time: "17:00",
      end_time: "21:00",
    }));
  };

  const addOccurrenceDate = () => {
    setValues((prev) => ({ ...prev, occurrence_dates: [...(prev.occurrence_dates || []), ""] }));
  };

  const updateOccurrenceDate = (index, value) => {
    setValues((prev) => ({
      ...prev,
      occurrence_dates: (prev.occurrence_dates || []).map((item, i) => (i === index ? value : item)),
    }));
  };

  const removeOccurrenceDate = (index) => {
    setValues((prev) => {
      const next = (prev.occurrence_dates || []).filter((_, i) => i !== index);
      return { ...prev, occurrence_dates: next.length ? next : [""] };
    });
  };

  const addPricingOption = () => {
    setValues((prev) => ({ ...prev, pricing_options: [...(prev.pricing_options || []), { ...EMPTY_PRICE_OPTION }] }));
  };

  const updatePricingOption = (index, field, value) => {
    setValues((prev) => ({
      ...prev,
      pricing_options: (prev.pricing_options || []).map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    }));
  };

  const removePricingOption = (index) => {
    setValues((prev) => {
      const next = (prev.pricing_options || []).filter((_, i) => i !== index);
      return { ...prev, pricing_options: next.length ? next : [{ ...EMPTY_PRICE_OPTION }] };
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const occurrenceDates = (values.occurrence_dates || [])
      .map((value) => String(value || "").slice(0, 10))
      .filter(Boolean)
      .filter((value, index, arr) => arr.indexOf(value) === index)
      .sort();
    const shouldAutofillRecurringStartDate =
      values.schedule_type === "recurring" &&
      values.recurring_mode === "dates" &&
      !values.start_date &&
      occurrenceDates.length > 0;
    const effectiveStartDate = shouldAutofillRecurringStartDate ? occurrenceDates[0] : values.start_date;
    if (shouldAutofillRecurringStartDate) {
      setValues((prev) => ({ ...prev, start_date: occurrenceDates[0] }));
    }
    const submitValues = shouldAutofillRecurringStartDate ? { ...values, start_date: effectiveStartDate } : values;

    setTouched({
      title: true,
      description: true,
      date: submitValues.schedule_type === "one_time",
      start_date: submitValues.schedule_type === "recurring",
      recurring_positions: submitValues.schedule_type === "recurring" && submitValues.recurring_mode === "rule",
      occurrence_dates: submitValues.schedule_type === "recurring" && submitValues.recurring_mode === "dates",
      pricing_options: true,
    });

    const submitErrors = validate(submitValues);
    if (Object.keys(submitErrors).length || submitting) return;

    const cleanedPricingOptions = (values.pricing_options || [])
      .map((row) => ({
        label: String(row?.label || "").trim(),
        price_rub: Number(row?.price_rub),
        note: String(row?.note || "").trim(),
      }))
      .filter((row) => row.label && Number.isFinite(row.price_rub) && row.price_rub >= 0)
      .map((row) => ({ ...row, price_rub: Math.round(row.price_rub), note: row.note || null }));

    const isRecurringRuleMode = isRecurring && values.recurring_mode === "rule";
    const payload = {
      title: values.title.trim(),
      description: values.description.trim(),
      location: trimOrNull(values.location),
      status: values.status,
      schedule_type: values.schedule_type,
      date: values.schedule_type === "one_time" ? values.date : null,
      start_date: isRecurring ? (effectiveStartDate || null) : null,
      start_time: isRecurring ? (values.start_time || null) : null,
      end_time: isRecurring ? (values.end_time || null) : null,
      recurring_rule: isRecurring
        ? (isRecurringRuleMode
            ? {
                freq: "MONTHLY",
                byweekday: values.recurring_weekday || "TU",
                bysetpos: [...(values.recurring_positions || [])].sort((a, b) => a - b),
              }
            : null)
        : null,
      occurrence_dates: isRecurring && !isRecurringRuleMode ? (occurrenceDates.length ? occurrenceDates : null) : null,
      pricing_options: cleanedPricingOptions.length ? cleanedPricingOptions : null,
      price: cleanedPricingOptions.length ? cleanedPricingOptions[0].price_rub : null,
      hosts: trimOrNull(values.hosts),
      duration_hint: trimOrNull(values.duration_hint),
      booking_hint: trimOrNull(values.booking_hint),
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
          <Button type="submit" form="event-form" disabled={submitting}>
            {submitting ? "Сохранение..." : RU.buttons.save}
          </Button>
        </div>
      }
    >
      <form id="event-form" className="space-y-3" onSubmit={handleSubmit}>
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
                {RU.labels.recurringStartDate}
                <Input
                  type="date"
                  value={values.start_date}
                  onChange={(e) => onFieldChange("start_date", e.target.value)}
                  onBlur={() => onFieldBlur("start_date")}
                />
                {touched.start_date && errors.start_date && <p className="mt-1 text-xs text-red-600">{errors.start_date}</p>}
              </label>

              <label className="block text-sm font-medium text-slate-700">
                {RU.labels.recurringMode}
                <select
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
                  value={values.recurring_mode}
                  onChange={(e) => onFieldChange("recurring_mode", e.target.value)}
                >
                  <option value="rule">{RU.labels.recurringModeRule}</option>
                  <option value="dates">{RU.labels.recurringModeDates}</option>
                </select>
              </label>
            </div>

            {values.recurring_mode === "rule" ? (
              <>
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
              </>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-slate-700">{RU.labels.occurrenceDates}</p>
                  <Button type="button" variant="secondary" onClick={addOccurrenceDate}>
                    {RU.labels.addDate}
                  </Button>
                </div>
                {(values.occurrence_dates || []).map((dateValue, index) => (
                  <div key={`occurrence-${index}`} className="flex items-center gap-2">
                    <Input
                      type="date"
                      value={dateValue}
                      onChange={(e) => updateOccurrenceDate(index, e.target.value)}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      className="px-3 py-2"
                      onClick={() => removeOccurrenceDate(index)}
                    >
                      {RU.buttons.delete}
                    </Button>
                  </div>
                ))}
                {touched.occurrence_dates && errors.occurrence_dates && (
                  <p className="text-xs text-red-600">{errors.occurrence_dates}</p>
                )}
              </div>
            )}

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
            disabled={isRolling || isRecurring}
          />
          {touched.date && errors.date && <p className="mt-1 text-xs text-red-600">{errors.date}</p>}
          {(isRolling || isRecurring) && (
            <p className="mt-1 text-xs text-slate-500">{RU.labels.eventDateOptionalHint}</p>
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
            rows={2}
          />
        </label>

        <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-slate-700">{RU.labels.prices}</p>
              <p className="text-xs text-slate-500">{RU.labels.pricesListHint}</p>
            </div>
            <Button type="button" variant="secondary" onClick={addPricingOption}>
              {RU.labels.addPriceOption}
            </Button>
          </div>

          {(values.pricing_options || []).map((row, index) => (
            <div key={`price-row-${index}`} className="grid grid-cols-1 gap-2 md:grid-cols-[1.2fr_0.8fr_1fr_auto] md:items-end">
              <label className="block text-sm font-medium text-slate-700">
                {RU.labels.priceOptionLabel}
                <Input value={row.label} onChange={(e) => updatePricingOption(index, "label", e.target.value)} />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                {RU.labels.priceOptionAmount}
                <Input
                  type="number"
                  min="0"
                  step="1"
                  value={row.price_rub}
                  onChange={(e) => updatePricingOption(index, "price_rub", e.target.value)}
                />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                {RU.labels.priceOptionNote}
                <Input value={row.note} onChange={(e) => updatePricingOption(index, "note", e.target.value)} />
              </label>
              <Button type="button" variant="ghost" className="h-10 px-3" onClick={() => removePricingOption(index)}>
                {RU.buttons.delete}
              </Button>
            </div>
          ))}

          {touched.pricing_options && errors.pricing_options && (
            <p className="text-xs text-red-600">{errors.pricing_options}</p>
          )}
        </div>

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
      </form>
    </Modal>
  );
}
