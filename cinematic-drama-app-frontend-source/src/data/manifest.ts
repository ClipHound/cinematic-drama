import type { Episode } from './catalog';
import type { InteractionManifest } from '../interaction/types';

export function createEmptyManifest(dramaId: string, episode: Episode): InteractionManifest {
  return {
    drama_id: dramaId,
    episode_id: episode.id,
    title: episode.title,
    video_url: episode.videoUrl,
    duration_ms: 0,
    manifest_version: '1.0.0',
    client_hints: {
      asset_base_url: '/assets/',
    },
    interaction_points: [],
  };
}
