import { cloneElement, isValidElement, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

export default function Dropdown({ trigger, items = [] }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    const onPointerDown = (event) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const handleToggle = (event) => {
    event.preventDefault();
    event.stopPropagation();
    setOpen((prev) => !prev);
  };

  const handleMenuPointerDown = (event) => {
    event.stopPropagation();
  };

  const triggerNode =
    isValidElement(trigger)
      ? cloneElement(trigger, {
          onClick: handleToggle,
        })
      : (
          <button type="button" onClick={handleToggle} className="inline-flex">
            {trigger}
          </button>
        );

  return (
    <div ref={rootRef} className="relative">
      {triggerNode}
      {open && (
        <div
          className="absolute right-0 mt-2 z-50 w-56 rounded-xl border border-slate-200 bg-white shadow-lg transition"
          onPointerDown={handleMenuPointerDown}
        >
          <div className="py-2">
            {items.map((item) => {
              const key = item.id || item.to || item.label;
              return item.to ? (
                <Link
                  key={key}
                  to={item.to}
                  onClick={() => setOpen(false)}
                  className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  {item.label}
                </Link>
              ) : (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    item.onClick?.();
                    setOpen(false);
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
