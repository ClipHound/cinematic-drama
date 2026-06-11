import type { InteractionManifest } from '../interaction/types';

export type Episode = {
  id: string;
  episodeNumber: number;
  title: string;
  durationLabel: string;
  videoUrl: string;
  interactionUrl?: string;
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

export type AiSearchResponse = {
  status: string;
  message: string;
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
