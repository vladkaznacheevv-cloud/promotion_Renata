import { AlertTriangle, Info } from "lucide-react";

const variants = {
  error: {
    wrapper: "border-red-200 bg-red-50 text-red-700",
    icon: "bg-red-100 text-red-600",
    label: "Ошибка",
    Icon: AlertTriangle,
  },
  info: {
    wrapper: "border-blue-200 bg-blue-50 text-blue-700",
    icon: "bg-blue-100 text-blue-600",
    label: "Инфо",
    Icon: Info,
  },
};

export default function ErrorBanner({ message, variant = "error" }) {
  if (!message) return null;
  const config = variants[variant] || variants.error;
  const Icon = config.Icon;

  return (
    <div className={`mb-6 flex items-start gap-3 rounded-xl border p-4 shadow-sm ${config.wrapper}`}>
      <div className={`mt-0.5 rounded-full p-2 ${config.icon}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-sm font-semibold">{config.label}</p>
        <p className="text-sm">{message}</p>
      </div>
    </div>
  );
}
