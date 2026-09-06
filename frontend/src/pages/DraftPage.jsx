import { Download, FileText, History, Search } from "lucide-react";
import { useEffect, useState } from "react";
import {
  apiErrorMessage,
  createDraft,
  downloadDraftBlob,
  getTemplate,
  listDrafts,
  listTemplates,
} from "../api/client";
import { useToast } from "../context/ToastContext";

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function DraftPage() {
  const [query, setQuery] = useState("");
  const [templates, setTemplates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [fieldValues, setFieldValues] = useState({});
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [downloading, setDownloading] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const { showToast } = useToast();

  useEffect(() => {
    listTemplates("").then(setTemplates).catch(() => {});
    listDrafts().then(setDrafts).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      listTemplates(query).then(setTemplates).catch(() => {});
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  async function handleSelectTemplate(templateId) {
    setResult(null);
    try {
      const detail = await getTemplate(templateId);
      setSelected(detail);
      setFieldValues({});
    } catch {
      showToast("Could not load this template.", "error");
    }
  }

  function handleFieldChange(key, value) {
    setFieldValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleGenerate() {
    if (!selected) return;
    setGenerating(true);
    try {
      const draft = await createDraft(selected.id, fieldValues);
      setResult(draft);
      setDrafts((prev) => [draft, ...prev]);
      showToast("Draft generated!", "success");
    } catch (err) {
      showToast(apiErrorMessage(err, "Failed to generate draft. Please try again."), "error");
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownload(draftId, templateName, format) {
    setDownloading(`${draftId}-${format}`);
    try {
      const blob = await downloadDraftBlob(draftId, format);
      triggerBlobDownload(blob, `${templateName.replace(/\s+/g, "_")}.${format}`);
    } catch (err) {
      showToast(apiErrorMessage(err, `Could not download the ${format.toUpperCase()}.`), "error");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 flex flex-col lg:flex-row gap-6">
      <div className="lg:w-1/3 flex flex-col gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-white mb-1">Draft a document</h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
            Search for a template to get started.
          </p>
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Bail Application, Affidavit..."
              className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-xl pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          {templates.length === 0 ? (
            <p className="text-sm text-slate-400">No matching templates.</p>
          ) : (
            templates.map((t) => (
              <button
                key={t.id}
                onClick={() => handleSelectTemplate(t.id)}
                className={`text-left rounded-xl border p-3.5 transition-colors ${
                  selected?.id === t.id
                    ? "border-indigo-500 border-2 bg-indigo-50 dark:bg-indigo-500/10"
                    : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-300"
                }`}
              >
                <div className="font-medium text-sm text-slate-900 dark:text-white">{t.name}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{t.description}</div>
              </button>
            ))
          )}
        </div>

        {drafts.length > 0 && (
          <div className="mt-4">
            <div className="flex items-center gap-1.5 mb-2">
              <History size={14} className="text-slate-400" />
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">My Drafts</h2>
            </div>
            <div className="flex flex-col gap-1.5">
              {drafts.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-slate-800 dark:text-slate-200 truncate">{d.template_name}</p>
                    <p className="text-xs text-slate-400">{new Date(d.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button
                      onClick={() => handleDownload(d.id, d.template_name, "docx")}
                      disabled={downloading === `${d.id}-docx`}
                      className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                    >
                      Word
                    </button>
                    <span className="text-slate-300">|</span>
                    <button
                      onClick={() => handleDownload(d.id, d.template_name, "pdf")}
                      disabled={downloading === `${d.id}-pdf`}
                      className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                    >
                      PDF
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="lg:w-2/3 flex flex-col gap-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6">
          {!selected ? (
            <p className="text-slate-400 text-sm">
              Select a template on the left to see its fields.
            </p>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-5">
                <FileText size={16} className="text-indigo-600 dark:text-indigo-400" />
                <h2 className="font-semibold text-slate-900 dark:text-white">{selected.name}</h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {selected.fields.map((field) => (
                  <div key={field.key} className={field.type === "textarea" ? "sm:col-span-2" : ""}>
                    <label className="block text-slate-700 dark:text-slate-300 text-sm font-medium mb-1">
                      {field.label}
                    </label>
                    {field.type === "textarea" ? (
                      <textarea
                        rows={3}
                        value={fieldValues[field.key] || ""}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    ) : (
                      <input
                        type="text"
                        value={fieldValues[field.key] || ""}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    )}
                  </div>
                ))}
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="w-full mt-6 bg-indigo-600 disabled:bg-indigo-300 hover:bg-indigo-700 text-white rounded-xl py-3 font-medium transition-colors"
              >
                {generating ? "Generating..." : "Generate Draft"}
              </button>
            </>
          )}
        </div>

        {result && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">
              Draft ready
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              Your "{result.template_name}" document has been generated. Download it below, or find it later in My Drafts.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => handleDownload(result.id, result.template_name, "docx")}
                disabled={downloading === `${result.id}-docx`}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              >
                <Download size={14} />
                {downloading === `${result.id}-docx` ? "Preparing..." : "Download .docx"}
              </button>
              <button
                onClick={() => handleDownload(result.id, result.template_name, "pdf")}
                disabled={downloading === `${result.id}-pdf`}
                className="flex items-center gap-1.5 border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              >
                <Download size={14} />
                {downloading === `${result.id}-pdf` ? "Preparing..." : "Download .pdf"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
