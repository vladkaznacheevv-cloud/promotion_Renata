export default function ErrorBanner({ message }) {
  if (!message) return null;

  return (
    <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-3 text-red-700">
      {message}
    </div>
  );
}
