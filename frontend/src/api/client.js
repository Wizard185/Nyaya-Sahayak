import axios from "axios";

const TOKEN_KEY = "nyaya_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

const client = axios.create({
  timeout: 300000,
});

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let onUnauthorized = null;
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(err);
  }
);

// Q&A calls can legitimately take longer than the default timeout.
const longClient = axios.create({ timeout: 120000 });
longClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
longClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401 && onUnauthorized) onUnauthorized();
    return Promise.reject(err);
  }
);

export function apiErrorMessage(err, fallback = "Something went wrong. Please try again.") {
  return err?.response?.data?.detail || fallback;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function signup(name, email, password) {
  const { data } = await client.post("/api/auth/signup", { name, email, password });
  return data;
}

export async function login(email, password) {
  const { data } = await client.post("/api/auth/login", { email, password });
  return data;
}

export async function fetchMe() {
  const { data } = await client.get("/api/auth/me");
  return data;
}

export async function updateProfile(name) {
  const { data } = await client.put("/api/auth/profile", { name });
  return data;
}

export async function updatePassword(currentPassword, newPassword) {
  const { data } = await client.put("/api/auth/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return data;
}

// ---------------------------------------------------------------------------
// Chats
// ---------------------------------------------------------------------------

export async function listChats() {
  const { data } = await client.get("/api/chats");
  return data;
}

export async function createChat() {
  const { data } = await client.post("/api/chats");
  return data;
}

export async function getChat(chatId) {
  const { data } = await client.get(`/api/chats/${chatId}`);
  return data;
}

export async function renameChat(chatId, title) {
  const { data } = await client.patch(`/api/chats/${chatId}`, { title });
  return data;
}

export async function deleteChat(chatId) {
  const { data } = await client.delete(`/api/chats/${chatId}`);
  return data;
}

export async function postMessage(chatId, query, language = "auto") {
  const { data } = await longClient.post(`/api/chats/${chatId}/messages`, { query, language });
  return data;
}

// ---------------------------------------------------------------------------
// Document drafter
// ---------------------------------------------------------------------------

export async function listTemplates(query = "") {
  const { data } = await client.get("/api/templates", { params: { query } });
  return data;
}

export async function getTemplate(templateId) {
  const { data } = await client.get(`/api/templates/${templateId}`);
  return data;
}

export async function createDraft(templateId, fieldValues) {
  const { data } = await longClient.post("/api/drafts", {
    template_id: templateId,
    field_values: fieldValues,
  });
  return data;
}

export async function listDrafts() {
  const { data } = await client.get("/api/drafts");
  return data;
}

export async function downloadDraftBlob(draftId, format = "docx") {
  const { data } = await client.get(`/api/drafts/${draftId}/download`, {
    params: { format },
    responseType: "blob",
  });
  return data;
}

// ---------------------------------------------------------------------------
// Guided scenarios
// ---------------------------------------------------------------------------

export async function startGuidedSession(scenario) {
  const { data } = await client.post("/api/guided/start", { scenario });
  return data;
}

export async function sendGuidedAnswer(stepId, answer, scenario) {
  const { data } = await client.post("/api/guided/next", {
    step_id: stepId,
    answer,
    scenario,
  });
  return data;
}

export async function getScenarios() {
  const { data } = await client.get("/api/scenarios");
  return data;
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

export async function checkHealth() {
  const { data } = await client.get("/api/health");
  return data;
}

export async function detectLanguage(text) {
  const { data } = await client.get("/api/detect", { params: { text } });
  return data;
}

export default client;
