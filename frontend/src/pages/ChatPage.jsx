import { Scale, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiErrorMessage, createChat, getChat, postMessage } from "../api/client";
import ChatBubble from "../components/ChatBubble";
import CitationCard from "../components/CitationCard";
import HallucinationBadge from "../components/HallucinationBadge";
import LanguageSelector from "../components/LanguageSelector";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";

const EXAMPLE_QUERIES = [
  "What is Section 498A IPC?",
  "How to file an RTI?",
  "My landlord won't return my deposit — what can I do?",
];

export default function ChatPage() {
  const { chatId } = useParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loadingChat, setLoadingChat] = useState(!!chatId);
  const [sending, setSending] = useState(false);
  const [lastCitations, setLastCitations] = useState(null);
  const [lastFlags, setLastFlags] = useState([]);
  const scrollRef = useRef(null);
  const { language } = useLanguage();
  const { showToast } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      setLastCitations(null);
      setLastFlags([]);
      return;
    }
    setLoadingChat(true);
    getChat(chatId)
      .then((chat) => {
        setMessages(chat.messages);
        const lastAssistant = [...chat.messages].reverse().find((m) => m.role === "assistant");
        setLastCitations(lastAssistant?.citations || null);
        setLastFlags(lastAssistant?.hallucination_flags || []);
      })
      .catch(() => {
        showToast("Could not load this chat.", "error");
        navigate("/chat");
      })
      .finally(() => setLoadingChat(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function submitQuery(text) {
    if (!text.trim() || sending) return;
    setSending(true);
    setInput("");

    let targetChatId = chatId;
    try {
      if (!targetChatId) {
        const chat = await createChat();
        targetChatId = chat.id;
        navigate(`/chat/${targetChatId}`, { replace: true });
      }

      const userMsg = { id: `u-${text}-${messages.length}`, role: "user", content: text };
      const loadingMsg = { id: "loading", role: "assistant", loading: true };
      setMessages((prev) => [...prev, userMsg, loadingMsg]);

      const assistantMsg = await postMessage(targetChatId, text, language);
      setMessages((prev) => [...prev.filter((m) => m.id !== "loading"), assistantMsg]);
      setLastCitations(assistantMsg.citations || []);
      setLastFlags(assistantMsg.hallucination_flags || []);
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== "loading"));
      showToast(apiErrorMessage(err, "Something went wrong while getting your answer."), "error");
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      submitQuery(input);
    }
  }

  if (loadingChat) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-sm text-slate-400">Loading chat...</p>
      </div>
    );
  }

  const showWelcome = messages.length === 0;

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 flex flex-col lg:flex-row gap-6 h-full">
      <div className="lg:w-2/3 flex flex-col h-full">
        {showWelcome ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
            <div className="w-14 h-14 rounded-2xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/30 mb-4">
              <Scale size={26} className="text-white" />
            </div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white mb-1">
              Ask a legal question
            </h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm mb-6 max-w-md">
              Get answers grounded in IPC, CrPC, the Constitution and BNS, with citations.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => submitQuery(q)}
                  className="text-xs bg-slate-100 dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 hover:text-indigo-700 dark:hover:text-indigo-300 text-slate-600 dark:text-slate-300 rounded-full px-3 py-1.5 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div ref={scrollRef} className="flex-1 flex flex-col gap-4 overflow-y-auto pr-1 mb-3">
            {messages.map((m) => (
              <ChatBubble key={m.id} message={m} />
            ))}
          </div>
        )}

        <div className="sticky bottom-0 bg-white dark:bg-slate-900 pt-2">
          <div className="flex gap-2 items-end">
            <textarea
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your legal question..."
              className="flex-1 resize-none border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              onClick={() => submitQuery(input)}
              disabled={sending || !input.trim()}
              className="bg-indigo-600 disabled:bg-indigo-300 hover:bg-indigo-700 text-white rounded-xl p-3 transition-colors shrink-0"
            >
              <Send size={18} />
            </button>
          </div>
          <div className="flex items-center justify-between mt-2 px-1">
            <LanguageSelector />
            <span className="text-xs text-slate-400">{input.length} chars</span>
          </div>
        </div>
      </div>

      <div className="lg:w-1/3 flex flex-col gap-4">
        {lastCitations === null ? (
          <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 rounded-xl p-6 text-sm text-slate-500 dark:text-slate-400">
            Citations and source sections will appear here after your first query.
          </div>
        ) : (
          <>
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">Cited Sections</h2>
              {lastCitations.length === 0 ? (
                <p className="text-xs text-slate-400">No sections were cited for this answer.</p>
              ) : (
                lastCitations.map((c) => <CitationCard key={c.section_id} citation={c} />)
              )}
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">Reliability</h2>
              <HallucinationBadge flags={lastFlags} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
