export default function EmptyState({ title, description, actionLabel, onAction }) {
  return (
    <div className="rounded-lg border border-dashed border-gray-200 p-6 text-sm text-gray-500">
      <p className="text-base font-semibold text-gray-900 mb-1">{title}</p>
      {description && <p className="mb-4 text-sm text-gray-500">{description}</p>}
      {actionLabel && (
        <button
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700"
          type="button"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
