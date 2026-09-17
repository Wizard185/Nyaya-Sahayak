import { Copy } from "lucide-react";
import { useState } from "react";
import { useToast } from "../context/ToastContext";

export default function CitationCard({ citation }) {
  const [expanded, setExpanded] = useState(false);
  const { showToast } = useToast();
  const isCase = citation.kind === "case";

  const handleCopy = (e) => {
    e.stopPropagation();
    const text = isCase
      ? `${citation.case_name} (${citation.citation}) — ${citation.court}\n${citation.excerpt}`
      : `${citation.section_id} (${citation.act}) — ${citation.title}\n${citation.excerpt}`;
    navigator.clipboard.writeText(text);
    showToast(isCase ? "Case copied to clipboard" : "Section copied to clipboard", "success");
  };

  const badgeClasses = isCase
    ? "bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300"
    : "bg-teal-100 dark:bg-teal-500/15 text-teal-700 dark:text-teal-300";
  const borderClass = isCase ? "border-indigo-500" : "border-teal-500";

  return (
    <div
      onClick={() => setExpanded((v) => !v)}
      className={`bg-white dark:bg-slate-800 border-l-4 ${borderClass} p-3 rounded-r-lg shadow-sm mb-2 cursor-pointer`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`${badgeClasses} font-mono text-xs px-1.5 py-0.5 rounded shrink-0`}>
            {isCase ? "CASE" : citation.section_id}
          </span>
          <span className="text-slate-500 dark:text-slate-400 text-xs truncate">
            {isCase ? citation.court : citation.act}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors shrink-0"
          title={isCase ? "Copy case" : "Copy section"}
        >
          <Copy size={14} />
        </button>
      </div>
      <div className="font-medium text-sm text-slate-800 dark:text-slate-100 mt-1">
        {isCase ? citation.case_name : citation.title}
      </div>
      {isCase && citation.citation && (
        <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{citation.citation}</div>
      )}
      <div
        className={`text-xs text-slate-500 dark:text-slate-400 italic mt-1 ${
          expanded ? "" : "line-clamp-2"
        }`}
      >
        {citation.excerpt}
      </div>
    </div>
  );
}
