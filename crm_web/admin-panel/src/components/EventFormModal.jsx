/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from "react";

import { RU } from "../i18n/ru";
import Button from "./ui/Button";
import Input from "./ui/Input";
import Modal from "./ui/Modal";

function validate(values) {
  const errors = {};

  if (!values.title.trim()) {
    errors.title = "Укажите название мероприятия.";
  }
  if (!values.description.trim()) {
    errors.description = "Добавьте описание мероприятия.";
  }
  if (!values.date) {
    errors.date = "Укажите дату мероприятия.";
  }

  return errors;
}

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
  });
  const [touched, setTouched] = useState({});

  useEffect(() => {
    if (initialData) {
      setValues({
        title: initialData.title || "",
        description: initialData.description || "",
        date: initialData.date || "",
        location: initialData.location || "",
        price: initialData.price ?? "",
        status: initialData.status || "active",
        link_getcourse: initialData.link_getcourse || "",
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
      });
    }
    setTouched({});
  }, [initialData, open]);

  const errors = useMemo(() => validate(values), [values]);
  const hasErrors = Object.keys(errors).length > 0;

  const onFieldChange = (field, value) => {
    setValues((prev) => ({ ...prev, [field]: value }));
  };

  const onFieldBlur = (field) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setTouched({ title: true, description: true, date: true });

    if (hasErrors || submitting) {
      return;
    }

    const payload = {
      title: values.title.trim(),
      description: values.description.trim(),
      date: values.date,
      location: values.location.trim() || null,
      price: values.price === "" ? null : Number(values.price),
      status: values.status,
      link_getcourse: values.link_getcourse.trim() || null,
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
          {RU.labels.date} *
          <Input
            type="date"
            value={values.date}
            onChange={(e) => onFieldChange("date", e.target.value)}
            onBlur={() => onFieldBlur("date")}
            required
          />
          {touched.date && errors.date && <p className="mt-1 text-xs text-red-600">{errors.date}</p>}
        </label>

        <label className="block text-sm font-medium text-slate-700">
          {RU.labels.location}
          <Input value={values.location} onChange={(e) => onFieldChange("location", e.target.value)} />
        </label>

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


