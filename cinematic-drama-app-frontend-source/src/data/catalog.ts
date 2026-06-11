import type { InteractionManifest } from '../interaction/types';

export type Episode = {
  id: string;
  episodeNumber: number;
  title: string;
  durationLabel: string;
  videoUrl: string;
  thumbnail?: string;
  interactionUrl?: string;
  totalEpisodes?: number;
  isLastEpisode?: boolean;
};

export type DramaItem = {
  id: string;
  title: string;
  subtitle: string;
  poster: string;
  cover: string;
  genre: string[];
  heat: string;
  score: string;
  description: string;
  episodes: Episode[];
  hasBranchNarrative?: boolean;
  totalEpisodes?: number;
};

export type AiSearchResult = {
  type: 'drama' | 'episode';
  dramaId: string;
  episodeNumber?: number;
  title: string;
  snippet?: string;
  poster?: string;
  subtitle?: string;
};

export type AiChatRole = 'user' | 'assistant';

export type AiChatMessageInput = {
  role: AiChatRole;
  content: string;
};

export type AiChatMode = 'fast' | 'smart';

export type AiRecommendation = {
  type: 'drama' | 'episode';
  id: string;
  dramaId: string;
  episodeNumber?: number | null;
  title: string;
  subtitle?: string;
  reason: string;
  imageUrl: string;
  href: string;
  score?: number;
};

export type AiChatEvent =
  | { type: 'message_start'; status?: string; mode?: AiChatMode }
  | { type: 'progress'; message: string }
  | { type: 'text_delta'; text: string }
  | { type: 'tool_call_start'; toolName: string; query?: string }
  | { type: 'tool_call_result'; toolName: string; count: number }
  | { type: 'recommendations'; items: AiRecommendation[] }
  | { type: 'message_end'; status?: string }
  | { type: 'error'; message: string };

export type AiSearchResponse = {
  status: string;
  message: string;
  results: AiSearchResult[];
};

export type SearchResponse = {
  results: AiSearchResult[];
};

const configuredApiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || '';

export const apiUrl = (path: string) => `${configuredApiBase}${path}`;

async function parseJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const message = typeof payload === 'object' && payload && 'message' in payload
      ? String((payload as { message?: unknown }).message)
      : fallbackMessage;
    throw new Error(message);
  }

  return payload as T;
}

export async function loadDramas() {
  const response = await fetch(apiUrl('/api/dramas'));
  const payload = await parseJson<{ dramas: DramaItem[] }>(response, '剧目列表加载失败');
  return payload.dramas;
}

export async function loadDrama(id: string) {
  const response = await fetch(apiUrl(`/api/dramas/${encodeURIComponent(id)}`));
  return parseJson<DramaItem>(response, '剧目详情加载失败');
}

export async function loadEpisode(dramaId: string, episodeNumber: number) {
  const response = await fetch(apiUrl(`/api/dramas/${encodeURIComponent(dramaId)}/episodes/${episodeNumber}`));
  return parseJson<Episode>(response, '剧集加载失败');
}

export async function loadEpisodeManifest(dramaId: string, episodeNumber: number) {
  const response = await fetch(apiUrl(`/api/dramas/${encodeURIComponent(dramaId)}/episodes/${episodeNumber}/interactions`));
  return parseJson<InteractionManifest>(response, '互动配置加载失败');
}

export async function requestAiSearch(query: string) {
  const response = await fetch(apiUrl('/api/ai/search'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  const payload = await parseJson<AiSearchResponse>(response, 'AI 搜索失败');
  return { ...payload, results: payload.results || [] };
}

export async function requestSearch(query: string) {
  const params = new URLSearchParams({ q: query });
  const response = await fetch(apiUrl(`/api/search?${params.toString()}`));
  const payload = await parseJson<SearchResponse>(response, '搜索失败');
  return { results: payload.results || [] };
}

function parseSseEvent(raw: string): AiChatEvent | null {
  const lines = raw.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith('event:'));
  const dataLines = lines.filter((line) => line.startsWith('data:'));
  if (!eventLine || !dataLines.length) return null;
  const eventType = eventLine.replace(/^event:\s*/, '').trim();
  const dataText = dataLines.map((line) => line.replace(/^data:\s*/, '')).join('\n');
  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(dataText) as Record<string, unknown>;
  } catch {
    payload = {};
  }

  if (eventType === 'message_start') return { type: 'message_start', status: String(payload.status || ''), mode: payload.mode === 'smart' ? 'smart' : 'fast' };
  if (eventType === 'progress') return { type: 'progress', message: String(payload.message || '') };
  if (eventType === 'text_delta') return { type: 'text_delta', text: String(payload.text || '') };
  if (eventType === 'tool_call_start') return { type: 'tool_call_start', toolName: String(payload.toolName || 'tool'), query: String(payload.query || '') };
  if (eventType === 'tool_call_result') return { type: 'tool_call_result', toolName: String(payload.toolName || 'tool'), count: Number(payload.count || 0) };
  if (eventType === 'recommendations') return { type: 'recommendations', items: Array.isArray(payload.items) ? payload.items as AiRecommendation[] : [] };
  if (eventType === 'message_end') return { type: 'message_end', status: String(payload.status || '') };
  if (eventType === 'error') return { type: 'error', message: String(payload.message || 'AI 搜索失败') };
  return null;
}

export async function streamAiChat(messages: AiChatMessageInput[], onEvent: (event: AiChatEvent) => void, options: { mode?: AiChatMode } = {}) {
  const response = await fetch(apiUrl('/api/ai/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, mode: options.mode || 'fast' }),
  });
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => null) as { message?: string } | null;
    throw new Error(payload?.message || 'AI 搜索失败');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\n\n/);
    buffer = parts.pop() || '';
    for (const part of parts) {
      const event = parseSseEvent(part.trim());
      if (event) onEvent(event);
    }
  }
  buffer += decoder.decode();
  const event = parseSseEvent(buffer.trim());
  if (event) onEvent(event);
}

// --- Branch Narrative types ---

export type BranchChoice = {
  choice_id: string;
  option_text: string;
  option_subtext: string;
  leads_to: string;
};

export type BranchNarrativeNode = {
  node_id: string;
  layer: number;
  route_tag: string;
  narrative: {
    title: string;
    paragraphs: string[];
    scene_description: string;
    characters_present: string[];
    mood: string;
  };
  visual: {
    prompt: string;
    reference_images: string[];
    style_tags: string[];
    image_url: string | null;
    image_path: string | null;
    status: string;
  };
  choices: BranchChoice[];
  audio_hint: {
    bgm_mood: string;
    sfx_suggestion: string;
  };
};

export type BranchRouteTag = {
  id: string;
  name: string;
  theme: string;
  emotion_arc: string;
};

export type BranchNarrative = {
  drama_id: string;
  branch_narrative_version: string;
  generated_at: string;
  metadata: {
    total_nodes: number;
    content_nodes: number;
    total_choices: number;
    endings_count: number;
    route_tags: string[];
    warnings: string[];
  };
  entry_node: string;
  route_tags: BranchRouteTag[];
  nodes: Record<string, BranchNarrativeNode>;
};

export async function loadBranchNarrative(dramaId: string) {
  const response = await fetch(apiUrl(`/api/dramas/${encodeURIComponent(dramaId)}/branch-narrative`));
  return parseJson<BranchNarrative>(response, '续写支线加载失败');
}
