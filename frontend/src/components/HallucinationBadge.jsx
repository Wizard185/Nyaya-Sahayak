import { AlertTriangle, CheckCircle2 } from "lucide-react";

export default function HallucinationBadge({ flags = [] }) {
  const isClean = flags.length === 0;

  return (
    <div
      className={`rounded-xl border p-3 text-sm flex items-start gap-2 ${
        isClean
          ? "bg-green-50 dark:bg-green-500/10 border-green-200 dark:border-green-500/30 text-green-700 dark:text-green-400"
          : "bg-amber-50 dark:bg-amber-500/10 border-amber-300 dark:border-amber-500/30 text-amber-700 dark:text-amber-400"
      }`}
    >
      {isClean ? (
        <CheckCircle2 size={18} className="shrink-0 mt-0.5" />
      ) : (
        <AlertTriangle size={18} className="shrink-0 mt-0.5" />
      )}
      <div>
        {isClean ? (
          <span className="font-medium">All citations verified</span>
        ) : (
          <>
            <span className="font-medium">Unverified references: </span>
            {flags.join(", ")}
          </>
        )}
      </div>
    </div>
  );
}
