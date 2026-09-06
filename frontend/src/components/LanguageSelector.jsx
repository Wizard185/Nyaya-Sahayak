import { ChevronDown, Languages } from "lucide-react";
import { LANGUAGES, useLanguage } from "../context/LanguageContext";

export default function LanguageSelector({ className = "" }) {
  const { language, setLanguage } = useLanguage();

  return (
    <div className={`relative inline-flex items-center ${className}`}>
      <Languages size={14} className="absolute left-2.5 text-slate-400 pointer-events-none" />
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value)}
        className="appearance-none border border-slate-300 dark:border-slate-700 rounded-lg text-sm pl-8 pr-7 py-1.5 text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        aria-label="Select language you are typing in"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
      <ChevronDown size={13} className="absolute right-2 text-slate-400 pointer-events-none" />
    </div>
  );
}
