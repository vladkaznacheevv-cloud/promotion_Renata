export function Table({ children, wrapperClassName = "", tableClassName = "" }) {
  const hasOverflowOverride = /\boverflow(?:-[xy])?-/.test(wrapperClassName);
  const overflowClass = hasOverflowOverride ? "" : "overflow-hidden";
  return (
    <div className={`${overflowClass} rounded-2xl border border-slate-200 bg-white ${wrapperClassName}`.trim()}>
      <table className={`min-w-full text-sm ${tableClassName}`}>{children}</table>
    </div>
  );
}

export function THead({ children }) {
  return <thead className="bg-slate-50 text-slate-500">{children}</thead>;
}

export function TBody({ children }) {
  return <tbody className="divide-y divide-slate-200 text-slate-700">{children}</tbody>;
}

export function TR({ children }) {
  return <tr>{children}</tr>;
}

export function TH({ children, className = "" }) {
  return <th className={`px-4 py-3 text-left font-semibold ${className}`}>{children}</th>;
}

export function TD({ children, className = "" }) {
  return <td className={`px-4 py-3 ${className}`}>{children}</td>;
}
