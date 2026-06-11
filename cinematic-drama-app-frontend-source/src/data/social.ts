import { apiUrl } from './catalog';
import { getDeviceId } from './device';

export type CommentItem = {
  id: number;
  deviceId: string;
  displayName: string;
  dramaId: string;
  episodeNumber?: number;
  content: string;
  likeCount: number;
  createdAt: string;
};

const deviceHeaders = () => ({ 'X-Device-Id': getDeviceId() });

async function parseJson<T>(response: Response, message: string): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.message || message);
  }
  return payload as T;
}

export async function loadFavorites() {
  const response = await fetch(apiUrl('/api/users/me/favorites'), {
    headers: deviceHeaders(),
  });
  const payload = await parseJson<{ favorites: Array<{ id: string }> }>(response, '收藏列表加载失败');
  return new Set(payload.favorites.map((item) => item.id));
}

export async function setFavorite(dramaId: string, favorited: boolean) {
  const response = await fetch(apiUrl(`/api/users/me/favorites/${encodeURIComponent(dramaId)}`), {
    method: favorited ? 'PUT' : 'DELETE',
    headers: deviceHeaders(),
  });
  return parseJson<{ status: string; favorited: boolean }>(response, '收藏状态更新失败');
}

export async function loadComments(dramaId: string, episodeNumber?: number) {
  const params = new URLSearchParams({ drama: dramaId });
  if (episodeNumber) params.set('episode', String(episodeNumber));
  const response = await fetch(apiUrl(`/api/comments?${params.toString()}`), {
    headers: deviceHeaders(),
  });
  const payload = await parseJson<{ comments: CommentItem[] }>(response, '评论加载失败');
  return payload.comments;
}

export async function postComment(dramaId: string, episodeNumber: number, content: string) {
  const response = await fetch(apiUrl('/api/comments'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...deviceHeaders(),
    },
    body: JSON.stringify({ dramaId, episodeNumber, content }),
  });
  return parseJson<{ status: string; id: number }>(response, '评论发送失败');
}
