export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex gap-2">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          onClick={() => onChange(tab.value)}
          className={`px-3 py-1.5 rounded-lg text-sm ${
            active === tab.value
              ? "bg-slate-900 text-white"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
