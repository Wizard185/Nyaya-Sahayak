import { Copy, Scale } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useToast } from "../context/ToastContext";
import HallucinationBadge from "./HallucinationBadge";
import LoadingDots from "./LoadingDots";

const LANGUAGE_LABELS = { en: "English", hi: "Hindi", kn: "Kannada" };

export default function ChatBubble({ message }) {
  const { showToast } = useToast();
  const isUser = message.role === "user";

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content || "");
    showToast("Copied to clipboard", "success");
  };

  if (isUser) {
    return (
      <div className="flex justify-end items-start gap-2">
        <div className="max-w-[80%] bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30 rounded-2xl rounded-tr-sm px-4 py-3">
          <p className="text-slate-800 dark:text-slate-100 whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-semibold shrink-0">
          U
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start items-start gap-2">
      <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center shrink-0">
        <Scale size={15} className="text-indigo-600 dark:text-indigo-400" />
      </div>
      <div className="max-w-[85%] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl rounded-tl-sm shadow-sm px-4 py-3 relative group">
        {message.loading ? (
          <LoadingDots />
        ) : (
          <>
            <div className="flex items-center justify-between gap-2 mb-1">
              {message.detected_language && message.detected_language !== "en" ? (
                <span className="text-xs text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-500/10 rounded px-1.5 py-0.5">
                  Translated from {LANGUAGE_LABELS[message.detected_language] || message.detected_language}
                </span>
              ) : (
                <span />
              )}
              <button
                onClick={handleCopy}
                className="text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors opacity-0 group-hover:opacity-100"
                title="Copy"
              >
                <Copy size={14} />
              </button>
            </div>

            <div className="prose prose-sm dark:prose-invert max-w-none text-slate-800 dark:text-slate-100 leading-relaxed">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>

            {message.hallucination_flags && message.hallucination_flags.length > 0 && (
              <div className="mt-3">
                <HallucinationBadge flags={message.hallucination_flags} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
