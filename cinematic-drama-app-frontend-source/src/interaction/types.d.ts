export type InteractionPoint = {
  id: string;
  start_ms: number;
  end_ms: number;
  component: string;
  title: string;
  emotion: string;
  priority: number;
  highlight_reason?: string;
  config?: Record<string, unknown>;
};

export type InteractionManifest = {
  drama_id: string;
  episode_id: string;
  title: string;
  video_url: string;
  duration_ms: number;
  manifest_version: string;
  client_hints?: {
    asset_base_url?: string;
  };
  interaction_points: InteractionPoint[];
};

export declare function renderInteraction(
  container: HTMLElement,
  props: {
    interactionPoint: InteractionPoint;
    assetBaseUrl: string;
    deviceTier: 'LOW' | 'MEDIUM' | 'HIGH';
    statsSnapshot: null;
    onInteract: (event: { eventType: string; actionData: Record<string, unknown> }) => void;
    onDismiss: (reason: string) => void;
  },
): void;

export declare function clearInteraction(container: HTMLElement): void;

export declare class InteractionTimeline {
  constructor(args: {
    manifest: InteractionManifest;
    onActivate?: (point: InteractionPoint) => void;
    onDismiss?: (point: InteractionPoint, reason: string) => void;
    onTick?: (ms: number) => void;
  });
  manifest: InteractionManifest;
  currentMs: number;
  running: boolean;
  play(externalClock?: boolean): void;
  pause(): void;
  seek(ms: number): void;
  sync(ms: number): void;
  dismissActive(reason: string): void;
}
