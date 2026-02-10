import { Link } from "react-router-dom";

export default function Dropdown({ trigger, items = [] }) {
  return (
    <div className="relative group">
      {trigger}
      <div className="absolute right-0 mt-2 w-56 rounded-xl border border-slate-200 bg-white shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition">
        <div className="py-2">
          {items.map((item) =>
            item.to ? (
              <Link
                key={item.label}
                to={item.to}
                className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                {item.label}
              </Link>
            ) : (
              <button
                key={item.label}
                type="button"
                onClick={item.onClick}
                className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                {item.label}
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}
