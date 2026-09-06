import {
  Check,
  FileText,
  ListTree,
  LogOut,
  MessageSquare,
  Moon,
  Pencil,
  Plus,
  Scale,
  Sun,
  Trash2,
  User,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createChat, deleteChat, listChats, renameChat } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";

export default function Sidebar() {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const { chatId } = useParams();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  async function refreshChats() {
    try {
      const data = await listChats();
      setChats(data);
    } catch {
      // silently ignore — chat list is non-critical
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshChats();
  }, []);

  async function handleNewChat() {
    const chat = await createChat();
    setChats((prev) => [chat, ...prev]);
    navigate(`/chat/${chat.id}`);
  }

  async function handleDelete(id, e) {
    e.stopPropagation();
    if (!window.confirm("Delete this chat?")) return;
    await deleteChat(id);
    setChats((prev) => prev.filter((c) => c.id !== id));
    if (chatId === id) navigate("/chat");
  }

  function startEdit(chat, e) {
    e.stopPropagation();
    setEditingId(chat.id);
    setEditTitle(chat.title);
  }

  async function commitEdit(id, e) {
    e.stopPropagation();
    const title = editTitle.trim();
    setEditingId(null);
    if (!title) return;
    await renameChat(id, title);
    setChats((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
  }

  return (
    <aside className="w-72 h-screen shrink-0 bg-slate-50 dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 flex flex-col">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-sm shadow-indigo-600/30">
          <Scale size={18} className="text-white" />
        </div>
        <span className="font-bold text-slate-900 dark:text-white">Nyaya Sahayak</span>
      </div>

      <div className="px-3 flex flex-col gap-1.5">
        <button
          onClick={handleNewChat}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-xl px-3 py-2.5 transition-colors"
        >
          <Plus size={16} />
          New chat
        </button>
        <button
          onClick={() => navigate("/draft")}
          className="flex items-center gap-2 text-slate-700 dark:text-slate-300 hover:bg-slate-200/60 dark:hover:bg-slate-800 text-sm font-medium rounded-xl px-3 py-2.5 transition-colors"
        >
          <FileText size={16} />
          Document Drafter
        </button>
        <button
          onClick={() => navigate("/guided")}
          className="flex items-center gap-2 text-slate-700 dark:text-slate-300 hover:bg-slate-200/60 dark:hover:bg-slate-800 text-sm font-medium rounded-xl px-3 py-2.5 transition-colors"
        >
          <ListTree size={16} />
          Get Guided
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 mt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 px-2 mb-2">
          Chats
        </p>
        {loading ? (
          <p className="text-sm text-slate-400 px-2">Loading...</p>
        ) : chats.length === 0 ? (
          <p className="text-sm text-slate-400 px-2">No chats yet.</p>
        ) : (
          <div className="flex flex-col gap-0.5">
            {chats.map((chat) => (
              <div
                key={chat.id}
                onClick={() => navigate(`/chat/${chat.id}`)}
                className={`group flex items-center gap-2 rounded-xl px-2.5 py-2 cursor-pointer text-sm transition-colors ${
                  chatId === chat.id
                    ? "bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-800"
                }`}
              >
                <MessageSquare size={15} className="shrink-0" />
                {editingId === chat.id ? (
                  <input
                    autoFocus
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.key === "Enter" && commitEdit(chat.id, e)}
                    className="flex-1 min-w-0 bg-white dark:bg-slate-800 border border-indigo-300 dark:border-indigo-700 rounded px-1.5 py-0.5 text-sm"
                  />
                ) : (
                  <span className="flex-1 min-w-0 truncate">{chat.title}</span>
                )}

                {editingId === chat.id ? (
                  <>
                    <button onClick={(e) => commitEdit(chat.id, e)} className="text-emerald-600">
                      <Check size={14} />
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); setEditingId(null); }} className="text-slate-400">
                      <X size={14} />
                    </button>
                  </>
                ) : (
                  <div className="hidden group-hover:flex items-center gap-1">
                    <button onClick={(e) => startEdit(chat, e)} className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
                      <Pencil size={13} />
                    </button>
                    <button onClick={(e) => handleDelete(chat.id, e)} className="text-slate-400 hover:text-red-600">
                      <Trash2 size={13} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 dark:border-slate-800 p-3 flex flex-col gap-1">
        <button
          onClick={toggleTheme}
          className="flex items-center gap-2 text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-800 text-sm rounded-xl px-2.5 py-2 transition-colors"
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <button
          onClick={() => navigate("/profile")}
          className="flex items-center gap-2 text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-800 text-sm rounded-xl px-2.5 py-2 transition-colors"
        >
          <User size={15} />
          <span className="truncate">{user?.name || "Profile"}</span>
        </button>
        <button
          onClick={logout}
          className="flex items-center gap-2 text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-800 text-sm rounded-xl px-2.5 py-2 transition-colors"
        >
          <LogOut size={15} />
          Log out
        </button>
      </div>
    </aside>
  );
}
