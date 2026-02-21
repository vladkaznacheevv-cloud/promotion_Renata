export default function Input({ className = "", ...props }) {
  return (
    <input
      className={`w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 ${className}`}
      {...props}
    />
  );
}
