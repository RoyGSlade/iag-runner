import axios from "axios";

const timeoutMs = Number(import.meta.env.VITE_API_TIMEOUT_MS);
const client = axios.create({
  baseURL: "/",
  timeout: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 60000
});

export async function createSession(payload) {
  const response = await client.post("/sessions", payload);
  return response.data;
}

export async function createCharacter(payload) {
  const response = await client.post("/characters", payload);
  return response.data;
}

export async function resolveTurn(payload) {
  const response = await client.post("/resolve_turn", payload);
  return response.data;
}

export async function fetchEras() {
  const response = await client.get("/eras");
  return Array.isArray(response.data) ? response.data : [];
}

export async function fetchRaces() {
  const response = await client.get("/races");
  return Array.isArray(response.data) ? response.data : [];
}

export async function fetchTrainings() {
  const response = await client.get("/trainings");
  return Array.isArray(response.data) ? response.data : [];
}

export async function fetchProfessions() {
  const response = await client.get("/professions");
  return Array.isArray(response.data) ? response.data : [];
}

export async function exportSession(sessionId) {
  const response = await client.post(`/sessions/${sessionId}/export`);
  return response.data;
}

export async function fetchThreads(sessionId) {
  const response = await client.get(`/sessions/${sessionId}/threads`);
  return response.data;
}

export async function fetchClocks(sessionId) {
  const response = await client.get(`/sessions/${sessionId}/clocks`);
  return response.data;
}

export async function importSession(payload) {
  const response = await client.post("/sessions/import", payload);
  return response.data;
}

export async function respawnCharacter(characterId) {
  const response = await client.post(`/characters/${characterId}/respawn`);
  return response.data;
}

export async function restartSession(sessionId) {
  const response = await client.post(`/sessions/${sessionId}/restart`);
  return response.data;
}

export default client;
