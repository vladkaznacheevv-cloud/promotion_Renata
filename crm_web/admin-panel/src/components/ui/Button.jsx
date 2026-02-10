const base = "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2";

const variants = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-700",
  secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
  danger: "border border-red-300 text-red-600 hover:bg-red-50",
  ghost: "text-slate-600 hover:bg-slate-100",
};

export default function Button({
  children,
  className = "",
  variant = "primary",
  type = "button",
  ...props
}) {
  return (
    <button type={type} className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}
