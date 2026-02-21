export default function SkeletonCard({ rows = 3, className = "" }) {
  return (
    <div className={`rounded-xl border border-gray-100 bg-white p-6 shadow-sm ${className}`}>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="h-3 w-full rounded-full shimmer" />
        ))}
      </div>
    </div>
  );
}
