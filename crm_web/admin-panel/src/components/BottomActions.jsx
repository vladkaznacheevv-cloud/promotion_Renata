import { X } from "lucide-react";

const colorClasses = {
  blue: { icon: "text-blue-600", hover: "hover:border-blue-400 hover:bg-blue-50" },
  green: { icon: "text-green-600", hover: "hover:border-green-400 hover:bg-green-50" },
  purple: { icon: "text-purple-600", hover: "hover:border-purple-400 hover:bg-purple-50" },
  yellow: { icon: "text-yellow-600", hover: "hover:border-yellow-400 hover:bg-yellow-50" },
  indigo: { icon: "text-indigo-600", hover: "hover:border-indigo-400 hover:bg-indigo-50" },
  gray: { icon: "text-gray-600", hover: "hover:border-gray-400 hover:bg-gray-50" },
};

export default function BottomActions({ actions, onClose }) {
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white shadow-xl z-50 border-t border-gray-200">
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Быстрые действия</h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg" type="button">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {actions.map((action) => {
            const cls = colorClasses[action.color] || colorClasses.gray;

            return (
              <button
                key={action.id}
                className={`p-4 rounded-lg border-2 border-dashed border-gray-300 transition-colors text-center ${cls.hover}`}
                type="button"
                onClick={action.onClick}
              >
                <div className={`mb-2 flex justify-center ${cls.icon}`}>{action.icon}</div>
                <span className="text-sm font-medium text-gray-700">{action.title}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
