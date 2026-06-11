import { apiUrl } from './catalog';
import type { DramaItem } from './catalog';
import { getDeviceId } from './device';

const deviceHeaders = () => ({ 'X-Device-Id': getDeviceId() });

export type UserProfile = {
  deviceId: string;
  displayName: string;
  bio: string;
  avatarText: string;
  stats: {
    watchedEpisodes: number;
    interactions: number;
    favorites: number;
  };
  continueWatching?: {
    episodeId?: string;
    dramaId: string;
    episodeNumber: number;
    title: string;
    progressMs?: number;
    durationMs?: number;
  };
};

export type FavoriteDramaItem = DramaItem & {
  favoriteAt?: string;
  firstEpisodeNumber?: number | null;
};

export type WatchProgressItem = {
  episodeId: string;
  dramaId: string;
  dramaTitle: string;
  episodeNumber: number;
  episodeTitle: string;
  title: string;
  progressMs: number;
  durationMs: number;
  updatedAt: string;
};

export type InteractionRecordItem = {
  eventId: string;
  eventType: string;
  dramaId: string;
  dramaTitle: string;
  episodeNumber: number;
  episodeTitle: string;
  pointId?: string | null;
  pointTitle?: string | null;
  atMs: number;
  actionData: Record<string, unknown>;
  receivedAt: string;
};

export type UserHistory = {
  watchProgress: WatchProgressItem[];
  interactions: InteractionRecordItem[];
};

async function parseJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await response.json().catch(() => null) as T | { message?: string } | null;
  if (!response.ok) {
    const message = typeof payload === 'object' && payload && 'message' in payload && payload.message
      ? String(payload.message)
      : fallbackMessage;
    throw new Error(message);
  }
  return payload as T;
}

export async function loadProfile() {
  const response = await fetch(apiUrl('/api/users/me/profile'), {
    headers: deviceHeaders(),
  });
  return parseJson<UserProfile>(response, '用户资料加载失败');
}

export async function loadFavoriteDramas() {
  const response = await fetch(apiUrl('/api/users/me/favorites'), {
    headers: deviceHeaders(),
  });
  const payload = await parseJson<{ favorites: FavoriteDramaItem[] }>(response, '收藏列表加载失败');
  return payload.favorites || [];
}

export async function loadHistory() {
  const response = await fetch(apiUrl('/api/users/me/history'), {
    headers: deviceHeaders(),
  });
  const payload = await parseJson<UserHistory>(response, '观看历史加载失败');
  return {
    watchProgress: payload.watchProgress || [],
    interactions: payload.interactions || [],
  };
}

export async function updateWatchProgress(
  episodeId: string | number,
  progressMs: number,
  durationMs: number,
  options: { keepalive?: boolean } = {},
) {
  const response = await fetch(apiUrl(`/api/users/me/progress/${encodeURIComponent(String(episodeId))}`), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...deviceHeaders(),
    },
    keepalive: options.keepalive,
    body: JSON.stringify({ progressMs, durationMs }),
  });
  return parseJson<{ status: string; id: number }>(response, '观看进度同步失败');
}
