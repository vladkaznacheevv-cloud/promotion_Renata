import { AlertTriangle } from "lucide-react";

export default function ErrorBanner({ message }) {
  if (!message) return null;

  return (
    <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 shadow-sm">
      <div className="mt-0.5 rounded-full bg-red-100 p-2 text-red-600">
        <AlertTriangle className="h-4 w-4" />
      </div>
      <div>
        <p className="text-sm font-semibold text-red-800">Ошибка</p>
        <p className="text-sm text-red-700">{message}</p>
      </div>
    </div>
  );
}
