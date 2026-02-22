import { useEffect } from "react";

export default function Modal({ open, onClose, title, children, footer }) {
  useEffect(() => {
    if (!open) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 p-3 sm:p-4">
      <div className="flex min-h-full items-center justify-center">
        <div className="flex w-full max-w-2xl max-h-[90vh] flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
          <div className="flex shrink-0 items-center justify-between border-b border-slate-200 px-4 py-3 sm:px-6 sm:py-4">
            <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
            >
              ✕
            </button>
          </div>
          <div
            className="min-h-0 flex-1 overflow-y-auto px-4 py-3 sm:px-6 sm:py-4"
            style={{ WebkitOverflowScrolling: "touch" }}
          >
            {children}
          </div>
          {footer && (
            <div className="shrink-0 border-t border-slate-200 bg-white px-4 py-3 sm:px-6 sm:py-4">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
