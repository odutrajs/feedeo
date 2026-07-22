import axios from "axios";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8005";

export const TOKEN_STORAGE_KEY = "feedeo.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export const http = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Anexa o JWT em toda requisição
http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 401 → sessão expirada: limpa token e manda para /login
// 402 → sem assinatura ativa: manda para /billing
http.interceptors.response.use(
  (res) => res,
  (error) => {
    if (typeof window !== "undefined" && axios.isAxiosError(error)) {
      const status = error.response?.status;
      const path = window.location.pathname;
      if (status === 401 && path !== "/login" && path !== "/register") {
        setToken(null);
        window.location.href = "/login";
      } else if (status === 402 && path !== "/billing") {
        window.location.href = "/billing";
      }
    }
    return Promise.reject(error);
  },
);

// ── Types ──────────────────────────────────────────────────────────

export interface User {
  id: number;
  name: string;
  email: string;
  role: "user" | "admin";
  subscription_status: "none" | "active" | "past_due" | "canceled";
  plan: string | null;
  current_period_end: string | null;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface BillingPlan {
  id: string;
  label: string;
  price_display: string;
}

export interface Project {
  id: number;
  title: string | null;
  topic: string;
  mode: "generative" | "creative" | "edit";
  language: string;
  status: string;
  config: Record<string, unknown>;
  error: string | null;
  workspace_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface BrandIdentity {
  primary_color: string;
  secondary_color: string;
  visual_style: string;
  text_theme: "dark" | "light";
}

export interface Workspace {
  id: number;
  name: string;
  description: string;
  logo_path: string | null;
  brand: Partial<BrandIdentity>;
  created_at: string;
  updated_at: string;
  video_count: number;
  post_count: number;
}

export interface SocialSlide {
  id: number;
  index: number;
  headline: string;
  body: string;
  image_prompt: string;
  image_path: string | null;
  composed_path: string | null;
}

export interface SocialPost {
  id: number;
  workspace_id: number;
  kind: "static" | "carousel";
  brief: string;
  status: "queued" | "running" | "completed" | "failed";
  caption: string;
  hashtags: string[];
  error: string | null;
  created_at: string;
  slides: SocialSlide[];
}

export interface WorkspaceDetail extends Workspace {
  projects: Project[];
  posts: SocialPost[];
}

export interface Scene {
  id: number;
  index: number;
  role: string;
  narration_text: string;
  visual_description: string;
  estimated_duration: number;
  start_time: number | null;
  end_time: number | null;
  image_prompt: string | null;
  motion: string | null;
  visual_source: "ai_image" | "segment" | "source_image";
  source_segment_id: number | null;
  source_asset_id: number | null;
}

export interface SourceSegment {
  id: number;
  source_id: number;
  index: number;
  start: number;
  end: number;
  duration: number;
  thumbnail_path: string | null;
  preview_path: string | null;
  transcript: string;
  description: string;
  tags: string[];
  score: number;
  score_reason: string;
  enabled: boolean;
  meta: Record<string, unknown>;
}

export interface SourceAsset {
  id: number;
  kind: "video" | "image";
  filename: string;
  path: string;
  status: "uploaded" | "processing" | "ready" | "failed";
  duration: number | null;
  width: number | null;
  height: number | null;
  error: string | null;
  created_at: string;
  segments: SourceSegment[];
}

export interface LibraryAsset {
  id: number;
  kind: "video" | "image";
  filename: string;
  path: string;
  thumbnail_path: string | null;
  duration: number | null;
  width: number | null;
  height: number | null;
  created_at: string;
}

export interface Asset {
  id: number;
  scene_id: number | null;
  kind: string;
  version: number;
  is_current: boolean;
  path: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface StageRun {
  id: number;
  stage: string;
  status: string;
  attempt: number;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  log: string;
  status_message: string;
}

export interface EditCut {
  id: number;
  source_id: number;
  index: number;
  start: number;
  end: number;
  duration: number;
  action: "keep" | "cut";
  reason: "voice_command" | "retake" | "silence" | "filler" | "speech" | "manual";
  transcript: string;
  detail: string;
  thumbnail_path: string | null;
  preview_path: string | null;
  meta: Record<string, unknown>;
}

export interface EditStyle {
  id: string;
  label: string;
  description: string;
}

export interface EditTransition {
  id: string;
  label: string;
  description: string;
  preview_path: string | null;
}

export const EDIT_ASPECTS: { id: string; label: string; hint: string }[] = [
  { id: "original", label: "Original", hint: "mantém o formato gravado" },
  { id: "9:16", label: "9:16", hint: "TikTok · Reels · Shorts" },
  { id: "4:5", label: "4:5", hint: "Feed do Instagram" },
  { id: "1:1", label: "1:1", hint: "Quadrado" },
  { id: "16:9", label: "16:9", hint: "YouTube" },
];

export const EDIT_AUDIO_OPTIONS: { id: string; label: string; hint: string }[] = [
  { id: "full", label: "Voz de estúdio", hint: "remove ruído, comprime e nivela a voz" },
  { id: "light", label: "Leve", hint: "só tira o ronco grave e nivela o volume" },
  { id: "off", label: "Original", hint: "áudio sem tratamento" },
];

export interface ProjectDetail extends Project {
  scenes: Scene[];
  stage_runs: StageRun[];
  assets: Asset[];
  sources: SourceAsset[];
  edit_cuts: EditCut[];
}

export const STAGE_LABELS: Record<string, string> = {
  script: "Roteiro",
  voice: "Narração",
  audio_sync: "Sincronização",
  visual_plan: "Plano visual",
  images: "Imagens",
  captions: "Legendas",
  render: "Montagem",
  publish_meta: "Publicação",
};

export const CREATIVE_STAGE_LABELS: Record<string, string> = {
  ...STAGE_LABELS,
  script: "Copy",
  visual_plan: "Seleção de trechos",
};

export const EDIT_STAGE_LABELS: Record<string, string> = {
  edit_analysis: "Análise dos cortes",
  edit_render: "Render final",
};

export function stageLabels(mode: Project["mode"]): Record<string, string> {
  if (mode === "edit") return EDIT_STAGE_LABELS;
  return mode === "creative" ? CREATIVE_STAGE_LABELS : STAGE_LABELS;
}

export const STAGE_ORDER = Object.keys(STAGE_LABELS);
export const EDIT_STAGE_ORDER = Object.keys(EDIT_STAGE_LABELS);

export function stageOrder(mode: Project["mode"]): string[] {
  return mode === "edit" ? EDIT_STAGE_ORDER : STAGE_ORDER;
}

export const LANGUAGES: { value: string; label: string }[] = [
  { value: "pt-BR", label: "Português (BR)" },
  { value: "en-US", label: "English (US)" },
  { value: "es-ES", label: "Español" },
  { value: "fr-FR", label: "Français" },
  { value: "de-DE", label: "Deutsch" },
  { value: "it-IT", label: "Italiano" },
];

// ── API calls ──────────────────────────────────────────────────────

export const api = {
  // ── Auth ────────────────────────────────────────────────────────

  register: (body: { name: string; email: string; password: string }) =>
    http.post<AuthResponse>("/api/auth/register", body).then((r) => r.data),

  login: (body: { email: string; password: string }) =>
    http.post<AuthResponse>("/api/auth/login", body).then((r) => r.data),

  me: () => http.get<User>("/api/auth/me").then((r) => r.data),

  // ── Billing (Stripe) ────────────────────────────────────────────

  listPlans: () => http.get<BillingPlan[]>("/api/billing/plans").then((r) => r.data),

  createCheckout: (plan: string) =>
    http.post<{ url: string }>("/api/billing/checkout", { plan }).then((r) => r.data),

  createBillingPortal: () =>
    http.post<{ url: string }>("/api/billing/portal", {}).then((r) => r.data),

  listProjects: () => http.get<Project[]>("/api/projects").then((r) => r.data),

  getProject: (id: number) =>
    http.get<ProjectDetail>(`/api/projects/${id}`).then((r) => r.data),

  getStages: (id: number) =>
    http.get<StageRun[]>(`/api/projects/${id}/stages`).then((r) => r.data),

  createProject: (body: {
    topic: string;
    title?: string;
    mode?: "generative" | "creative" | "edit";
    language?: string;
    config?: Record<string, unknown>;
    autostart?: boolean;
    workspace_id?: number | null;
  }) => http.post<Project>("/api/projects", body).then((r) => r.data),

  // ── Workspaces (projetos do usuário) e posts sociais ───────────

  listWorkspaces: () => http.get<Workspace[]>("/api/workspaces").then((r) => r.data),

  createWorkspace: (body: { name: string; description: string }) =>
    http.post<Workspace>("/api/workspaces", body).then((r) => r.data),

  getWorkspace: (id: number) =>
    http.get<WorkspaceDetail>(`/api/workspaces/${id}`).then((r) => r.data),

  updateWorkspace: (
    id: number,
    body: { name?: string; description?: string; brand?: BrandIdentity },
  ) => http.patch<Workspace>(`/api/workspaces/${id}`, body).then((r) => r.data),

  deleteWorkspace: (id: number) =>
    http.delete(`/api/workspaces/${id}`).then((r) => r.data),

  uploadWorkspaceLogo: (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return http
      .put<Workspace>(`/api/workspaces/${id}/logo`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  deleteWorkspaceLogo: (id: number) =>
    http.delete<Workspace>(`/api/workspaces/${id}/logo`).then((r) => r.data),

  createSocialPost: (
    workspaceId: number,
    body: { kind: "static" | "carousel"; brief: string; language?: string },
  ) =>
    http
      .post<SocialPost>(`/api/workspaces/${workspaceId}/posts`, body)
      .then((r) => r.data),

  regenerateSocialPost: (workspaceId: number, postId: number) =>
    http
      .post<SocialPost>(`/api/workspaces/${workspaceId}/posts/${postId}/regenerate`, {})
      .then((r) => r.data),

  deleteSocialPost: (workspaceId: number, postId: number) =>
    http.delete(`/api/workspaces/${workspaceId}/posts/${postId}`).then((r) => r.data),

  listEditStyles: () =>
    http.get<EditStyle[]>("/api/projects/edit-styles").then((r) => r.data),

  listEditTransitions: () =>
    http.get<EditTransition[]>("/api/projects/edit-transitions").then((r) => r.data),

  updateEditCut: (projectId: number, cutId: number, action: "keep" | "cut") =>
    http
      .patch(`/api/projects/${projectId}/edit-cuts/${cutId}`, { action })
      .then((r) => r.data),

  runProject: (id: number, fromStage?: string) =>
    http.post<Project>(`/api/projects/${id}/run`, { from_stage: fromStage ?? null }).then((r) => r.data),

  approve: (id: number) =>
    http.post<Project>(`/api/projects/${id}/approve`, {}).then((r) => r.data),

  reject: (id: number) =>
    http.post<Project>(`/api/projects/${id}/reject`, {}).then((r) => r.data),

  updateScene: (projectId: number, sceneId: number, body: Partial<Scene>) =>
    http.patch(`/api/projects/${projectId}/scenes/${sceneId}`, body).then((r) => r.data),

  regenerateImage: (projectId: number, sceneId: number, promptOverride?: string) =>
    http
      .post(`/api/projects/${projectId}/scenes/${sceneId}/regenerate-image`, {
        prompt_override: promptOverride ?? null,
      })
      .then((r) => r.data),

  // ── Fontes (mídia enviada para criativos) ──────────────────────

  uploadSources: (projectId: number, files: File[]) => {
    const form = new FormData();
    for (const file of files) form.append("files", file);
    return http
      .post<SourceAsset[]>(`/api/projects/${projectId}/sources`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 0,
      })
      .then((r) => r.data);
  },

  listSources: (projectId: number) =>
    http.get<SourceAsset[]>(`/api/projects/${projectId}/sources`).then((r) => r.data),

  deleteSource: (projectId: number, sourceId: number) =>
    http.delete(`/api/projects/${projectId}/sources/${sourceId}`).then((r) => r.data),

  reanalyzeSource: (projectId: number, sourceId: number) =>
    http
      .post<SourceAsset>(`/api/projects/${projectId}/sources/${sourceId}/reanalyze`, {})
      .then((r) => r.data),

  updateSegment: (projectId: number, segmentId: number, body: { enabled?: boolean }) =>
    http
      .patch<SourceSegment>(`/api/projects/${projectId}/sources/segments/${segmentId}`, body)
      .then((r) => r.data),

  attachFromLibrary: (projectId: number, libraryIds: number[]) =>
    http
      .post<SourceAsset[]>(`/api/projects/${projectId}/sources/from-library`, {
        library_ids: libraryIds,
      })
      .then((r) => r.data),

  // ── Biblioteca de mídia reutilizável ───────────────────────────

  listLibrary: () => http.get<LibraryAsset[]>("/api/library").then((r) => r.data),

  uploadToLibrary: (files: File[]) => {
    const form = new FormData();
    for (const file of files) form.append("files", file);
    return http
      .post<LibraryAsset[]>("/api/library", form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 0,
      })
      .then((r) => r.data);
  },

  deleteLibraryAsset: (assetId: number) =>
    http.delete(`/api/library/${assetId}`).then((r) => r.data),

  // ── Instagram / Publishing ──────────────────────────────────────

  getInstagramStatus: (workspaceId: number) =>
    http.get<InstagramStatus>(`/api/auth/instagram/status`, { params: { workspace_id: workspaceId } }).then((r) => r.data),

  disconnectInstagram: (workspaceId: number) =>
    http.delete(`/api/auth/instagram/disconnect`, { params: { workspace_id: workspaceId } }).then((r) => r.data),

  publishToInstagram: (projectId: number) =>
    http.post<PublicationResponse>(`/api/publishing/publish`, { project_id: projectId, platform: "instagram_reels" }).then((r) => r.data),

  publishPostToInstagram: (socialPostId: number) =>
    http.post<PublicationResponse>(`/api/publishing/publish-post`, { social_post_id: socialPostId }).then((r) => r.data),

  listPublications: (params: { projectId?: number; socialPostId?: number; workspaceId?: number }) =>
    http.get<PublicationResponse[]>(`/api/publishing/publications`, {
      params: {
        project_id: params.projectId,
        social_post_id: params.socialPostId,
        workspace_id: params.workspaceId,
      },
    }).then((r) => r.data),

  // ── Scheduling ─────────────────────────────────────────────────────

  schedulePost: (params: { socialPostId?: number; projectId?: number; scheduledAt: string }) =>
    http.post<ScheduleResponse>(`/api/scheduler/schedule`, {
      social_post_id: params.socialPostId,
      project_id: params.projectId,
      scheduled_at: params.scheduledAt,
    }).then((r) => r.data),

  cancelSchedule: (publicationId: number) =>
    http.post(`/api/scheduler/cancel-schedule`, { publication_id: publicationId }).then((r) => r.data),
};

export interface ScheduleResponse {
  publication_id: number;
  job_id: string;
  scheduled_at: string;
}

export interface InstagramStatus {
  connected: boolean;
  account_id?: number;
  name?: string;
  profile_picture_url?: string | null;
}

export interface PublicationResponse {
  id: number;
  project_id: number | null;
  social_post_id: number | null;
  account_id: number;
  status: "scheduled" | "uploading" | "published" | "failed" | "cancelled";
  scheduled_at: string | null;
  published_at: string | null;
  external_id: string | null;
  error: string | null;
}

export function instagramConnectUrl(workspaceId: number): string {
  const token = getToken();
  const params = new URLSearchParams({ workspace_id: String(workspaceId) });
  if (token) params.set("token", token);
  return `${API_BASE}/api/auth/instagram/connect?${params.toString()}`;
}

export function isAxios402(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 402;
}

// ── Helpers ────────────────────────────────────────────────────────

export function mediaUrl(path: string): string {
  return `${API_BASE}/media/${path}`;
}

const ACTIVE_STATUSES = new Set(["queued", "running"]);

export function isActive(status: string): boolean {
  return ACTIVE_STATUSES.has(status);
}

/** Formata Date para value de <input type="date|time"> no horário local. */
export function toLocalDateValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function toLocalTimeValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Converte date+time locais (YYYY-MM-DD + HH:mm) para ISO UTC. */
export function localDateTimeToISO(date: string, time: string): string {
  return new Date(`${date}T${time}`).toISOString();
}

/**
 * Exibe scheduled_at no horário local.
 * A API pode devolver datetime sem "Z"; tratamos como UTC nesse caso.
 */
export function formatScheduledAt(iso: string): string {
  const hasTz = iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso);
  const d = new Date(hasTz ? iso : `${iso}Z`);
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Poll só durante upload real — agendamento futuro NÃO faz polling. */
export function shouldPollPublications(pubs: PublicationResponse[] | undefined): number | false {
  if (!pubs?.length) return false;
  const needsPoll = pubs.some(
    (p) =>
      p.status === "uploading" ||
      // publicação imediata (sem scheduled_at futuro)
      (p.status === "scheduled" && !p.scheduled_at),
  );
  return needsPoll ? 5_000 : false;
}
