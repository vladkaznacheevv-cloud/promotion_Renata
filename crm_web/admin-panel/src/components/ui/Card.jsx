export function Card({ children, className = "" }) {
  return <div className={`h-full rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}>{children}</div>;
}

export function CardHeader({ children, className = "" }) {
  return <div className={`px-5 pt-5 lg:px-6 lg:pt-6 ${className}`}>{children}</div>;
}

export function CardContent({ children, className = "" }) {
  return <div className={`px-5 pb-5 lg:px-6 lg:pb-6 ${className}`}>{children}</div>;
}
