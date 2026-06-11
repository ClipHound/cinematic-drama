import { apiUrl } from './catalog';
import { getDeviceId } from './device';

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
    dramaId: string;
    episodeNumber: number;
    title: string;
  };
};

export async function loadProfile() {
  const response = await fetch(apiUrl('/api/users/me/profile'), {
    headers: { 'X-Device-Id': getDeviceId() },
  });
  const payload = await response.json().catch(() => null) as UserProfile | { message?: string } | null;
  if (!response.ok) {
    throw new Error(payload && 'message' in payload && payload.message ? payload.message : '用户资料加载失败');
  }
  return payload as UserProfile;
}
