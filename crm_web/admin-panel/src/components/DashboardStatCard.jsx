import { ChevronDown, ChevronUp } from "lucide-react";

export default function DashboardStatCard({ title, value, change, changeType, icon }) {
  const changeClass =
    changeType === "positive"
      ? "text-green-600"
      : changeType === "negative"
        ? "text-red-600"
        : "text-gray-600";

  return (
    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
          <div className={`mt-2 flex items-center text-sm ${changeClass}`}>
            {changeType === "positive" && <ChevronUp className="h-4 w-4 mr-1" />}
            {changeType === "negative" && <ChevronDown className="h-4 w-4 mr-1" />}
            {change}
          </div>
        </div>
        <div className="text-indigo-600">{icon}</div>
      </div>
    </div>
  );
}
