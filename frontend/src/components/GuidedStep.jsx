import { ArrowRight } from "lucide-react";

export default function GuidedStep({ step, onAnswer }) {
  if (!step) return null;

  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-md dark:shadow-none border border-transparent dark:border-slate-700 p-8">
      <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-6">{step.question}</h3>
      <div className="flex flex-col gap-3">
        {step.options.map((option) => (
          <button
            key={option}
            onClick={() => onAnswer(option)}
            className="flex items-center justify-between w-full text-left bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4 hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-all"
          >
            <span className="text-slate-700 dark:text-slate-200">{option}</span>
            <ArrowRight size={18} className="text-slate-400" />
          </button>
        ))}
      </div>
    </div>
  );
}
