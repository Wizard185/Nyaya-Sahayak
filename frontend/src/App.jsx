import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { checkHealth } from "./api/client";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LanguageProvider } from "./context/LanguageContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ToastProvider } from "./context/ToastContext";
import ChatPage from "./pages/ChatPage";
import DraftPage from "./pages/DraftPage";
import GuidedPage from "./pages/GuidedPage";
import LoginPage from "./pages/LoginPage";
import ProfilePage from "./pages/ProfilePage";
import SignupPage from "./pages/SignupPage";

function HealthBanner() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    checkHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "error", ollama: false, pinecone: false, mongodb: false }));
  }, []);

  if (!health) return null;

  const warnings = [];
  if (!health.ollama) warnings.push("Ollama is not running. Start it with: ollama serve");
  if (!health.pinecone) warnings.push("Pinecone is unreachable. Check PINECONE_API_KEY and your internet connection.");
  if (!health.mongodb) warnings.push("MongoDB is unreachable. Check that mongod is running.");

  if (warnings.length === 0) return null;

  return (
    <div className="bg-amber-50 dark:bg-amber-500/10 border-b border-amber-200 dark:border-amber-500/30 text-amber-800 dark:text-amber-400 text-sm">
      {warnings.map((w, i) => (
        <div key={i} className="px-4 py-2 text-center font-medium">
          ⚠ {w}
        </div>
      ))}
    </div>
  );
}

function AuthLayout() {
  const { loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white dark:bg-slate-900">
        <p className="text-sm text-slate-400">Loading...</p>
      </div>
    );
  }
  return (
    <ProtectedRoute>
      <div className="flex flex-col min-h-screen">
        <HealthBanner />
        <Layout />
      </div>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <LanguageProvider>
          <ToastProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />

              <Route element={<AuthLayout />}>
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/chat/:chatId" element={<ChatPage />} />
                <Route path="/draft" element={<DraftPage />} />
                <Route path="/guided" element={<GuidedPage />} />
                <Route path="/profile" element={<ProfilePage />} />
              </Route>

              <Route path="/" element={<Navigate to="/chat" replace />} />
              <Route path="*" element={<Navigate to="/chat" replace />} />
            </Routes>
          </ToastProvider>
        </LanguageProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
