import { Check } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createChat, postMessage, sendGuidedAnswer, startGuidedSession } from "../api/client";
import GuidedStep from "../components/GuidedStep";
import { useToast } from "../context/ToastContext";

const SCENARIOS = [
  { id: "landlord", title: "Landlord Dispute", icon: "🏠" },
  { id: "consumer", title: "Consumer Complaint", icon: "🛒" },
  { id: "employment", title: "Employment Issue", icon: "💼" },
];

const MAX_VISIBLE_STEPS = 5;

export default function GuidedPage() {
  const [scenario, setScenario] = useState(null);
  const [step, setStep] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const navigate = useNavigate();
  const { showToast } = useToast();

  async function handleSelectScenario(scenarioId) {
    setScenario(scenarioId);
    setLoading(true);
    setHistory([]);
    try {
      const data = await startGuidedSession(scenarioId);
      setStep(data);
    } catch {
      showToast("Could not start guided session.", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnswer(answer) {
    if (!step || !scenario) return;
    setLoading(true);
    try {
      const data = await sendGuidedAnswer(step.step_id, answer, scenario);
      setHistory((prev) => [...prev, step.progress]);
      setStep(data);
    } catch {
      showToast("Something went wrong. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  }

  function handleStartOver() {
    setScenario(null);
    setStep(null);
    setHistory([]);
  }

  async function handleAskFollowup() {
    if (!step?.result) return;
    const summary = `I went through the guided ${scenario} scenario. Here is my situation summary:\n\n${step.result}\n\nCan you tell me more about my options?`;
    try {
      const chat = await createChat();
      await postMessage(chat.id, summary, "en");
      navigate(`/chat/${chat.id}`);
    } catch {
      showToast("Could not start a chat from this summary.", "error");
    }
  }

  const isDone = step && step.result;
  const progressSteps = [...history, step?.progress].filter(Boolean).slice(-MAX_VISIBLE_STEPS);

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <h1 className="text-xl font-semibold text-slate-900 dark:text-white mb-1">Get Guided</h1>
      <p className="text-slate-500 dark:text-slate-400 text-sm mb-6">
        Answer a few questions and get a tailored rights summary
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            onClick={() => handleSelectScenario(s.id)}
            className={`bg-white dark:bg-slate-900 rounded-xl border p-6 text-left hover:shadow-md dark:hover:shadow-none transition-shadow ${
              scenario === s.id ? "border-indigo-500 border-2" : "border-slate-200 dark:border-slate-800"
            }`}
          >
            <div className="text-3xl mb-2">{s.icon}</div>
            <div className="font-medium text-slate-900 dark:text-white">{s.title}</div>
          </button>
        ))}
      </div>

      {step && !isDone && (
        <div className="flex items-center justify-center gap-2 mb-8">
          {progressSteps.map((p, idx) => {
            const isLast = idx === progressSteps.length - 1;
            return (
              <div key={idx} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold ${
                    isLast ? "bg-indigo-600 text-white" : "bg-teal-500 text-white"
                  }`}
                >
                  {isLast ? p : <Check size={14} />}
                </div>
                {idx < progressSteps.length - 1 && (
                  <div className="w-8 h-0.5 bg-slate-300 dark:bg-slate-700" />
                )}
              </div>
            );
          })}
        </div>
      )}

      {loading && !step && (
        <p className="text-center text-slate-400 text-sm">Loading...</p>
      )}

      {step && !isDone && <GuidedStep step={step} onAnswer={handleAnswer} />}

      {isDone && (
        <div className="bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30 rounded-2xl p-8">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
            Your Rights Summary
          </h3>
          <div className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap leading-relaxed mb-6">
            {step.result}
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleAskFollowup}
              className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            >
              Ask Follow-up Question
            </button>
            <button
              onClick={handleStartOver}
              className="border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            >
              Start Over
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
