import { Copy } from "lucide-react";
import { useState } from "react";
import { useToast } from "../context/ToastContext";

export default function CitationCard({ citation }) {
  const [expanded, setExpanded] = useState(false);
  const { showToast } = useToast();

  const handleCopy = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(
      `${citation.section_id} (${citation.act}) — ${citation.title}\n${citation.excerpt}`
    );
    showToast("Section copied to clipboard", "success");
  };

  return (
    <div
      onClick={() => setExpanded((v) => !v)}
      className="bg-white dark:bg-slate-800 border-l-4 border-teal-500 p-3 rounded-r-lg shadow-sm mb-2 cursor-pointer"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="bg-teal-100 dark:bg-teal-500/15 text-teal-700 dark:text-teal-300 font-mono text-xs px-1.5 py-0.5 rounded">
            {citation.section_id}
          </span>
          <span className="text-slate-500 dark:text-slate-400 text-xs">{citation.act}</span>
        </div>
        <button
          onClick={handleCopy}
          className="text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
          title="Copy section"
        >
          <Copy size={14} />
        </button>
      </div>
      <div className="font-medium text-sm text-slate-800 dark:text-slate-100 mt-1">{citation.title}</div>
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
