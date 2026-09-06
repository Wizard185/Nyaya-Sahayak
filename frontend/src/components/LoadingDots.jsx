export default function LoadingDots() {
  return (
    <div className="flex items-center gap-1 px-2 py-1" aria-label="Loading">
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce delay-100" />
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce delay-200" />
    </div>
  );
}
