const variants = {
  vip: "bg-purple-50 text-purple-700 border-purple-200",
  active: "bg-green-50 text-green-700 border-green-200",
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  cancelled: "bg-rose-50 text-rose-700 border-rose-200",
  finished: "bg-slate-50 text-slate-600 border-slate-200",
  default: "bg-slate-50 text-slate-600 border-slate-200",
};

export default function Badge({ children, variant = "default", className = "" }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
}
