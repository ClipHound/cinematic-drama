import { ChevronLeft, ListVideo, Pause, Play, Sparkles } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorState, LoadingState } from '../components/PageState';
import { loadDrama, loadEpisode, loadEpisodeManifest } from '../data/catalog';
import type { DramaItem, Episode } from '../data/catalog';
import { createEmptyManifest } from '../data/manifest';
import { updateWatchProgress } from '../data/profile';
import { clearInteraction, renderInteraction } from '../interaction/components.js';
import { LocalEventQueue } from '../interaction/queue';
import { InteractionTimeline } from '../interaction/timeline.js';
import type { InteractionManifest, InteractionPoint, InteractionTimeline as InteractionTimelineType } from '../interaction/types';

const formatTime = (ms: number) => {
  const total = Math.floor(ms / 1000);
  const minutes = Math.floor(total / 60).toString().padStart(2, '0');
  const seconds = (total % 60).toString().padStart(2, '0');
  return `${minutes}:${seconds}`;
};

export default function PlayerPage() {
  const [searchParams] = useSearchParams();
  const dramaId = searchParams.get('drama') || 'furao-dadi';
  const episodeNumber = Number(searchParams.get('episode') || '1') || 1;
  const [drama, setDrama] = useState<DramaItem | null>(null);
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [manifest, setManifest] = useState<InteractionManifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [manifestStatus, setManifestStatus] = useState<string | null>(null);
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const layerRef = useRef<HTMLDivElement | null>(null);
  const timelineRef = useRef<InteractionTimelineType | null>(null);
  const queueRef = useRef<LocalEventQueue | null>(null);
  const episodeRef = useRef<Episode | null>(null);
  const lastProgressSyncRef = useRef(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentMs, setCurrentMs] = useState(0);
  const [showBranchPrompt, setShowBranchPrompt] = useState(false);

  const progress = useMemo(() => {
    if (!manifest?.duration_ms) return 0;
    return Math.min(100, Math.max(0, (currentMs / manifest.duration_ms) * 100));
  }, [currentMs, manifest?.duration_ms]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    setManifestStatus(null);
    try {
      const [loadedDrama, loadedEpisode] = await Promise.all([
        loadDrama(dramaId).catch(() => null),
        loadEpisode(dramaId, episodeNumber),
      ]);
      setDrama(loadedDrama);
      setEpisode(loadedEpisode);

      const remoteManifest = await loadEpisodeManifest(dramaId, episodeNumber).catch((err) => {
        setManifestStatus(err instanceof Error ? err.message : '互动配置加载失败');
        return null;
      });
      setManifest(remoteManifest || createEmptyManifest(dramaId, loadedEpisode));
    } catch (err) {
      setError(err instanceof Error ? err.message : '剧集加载失败');
    } finally {
      setLoading(false);
    }
  }, [dramaId, episodeNumber]);

  useEffect(() => {
    queueRef.current = new LocalEventQueue(setQueueStatus);
    void reload();
  }, [reload]);

  useEffect(() => {
    episodeRef.current = episode;
  }, [episode]);

  const getVideoDurationMs = (video: HTMLVideoElement | null) => {
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return manifest?.duration_ms || 0;
    return Math.round(video.duration * 1000);
  };

  const syncWatchProgress = useCallback(
    (options: { force?: boolean; keepalive?: boolean; progressMs?: number; durationMs?: number } = {}) => {
      const currentEpisode = episodeRef.current;
      const video = videoRef.current;
      if (!currentEpisode || !video) return;
      const currentTime = Number.isFinite(video.currentTime) && video.currentTime > 0 ? video.currentTime : 0;
      const durationMs = options.durationMs ?? getVideoDurationMs(video);
      const progressMs = options.progressMs ?? Math.max(0, Math.round(currentTime * 1000));
      if (!durationMs && !progressMs) return;

      const now = Date.now();
      if (!options.force && now - lastProgressSyncRef.current < 5000) return;
      lastProgressSyncRef.current = now;

      updateWatchProgress(currentEpisode.id, progressMs, durationMs || progressMs, { keepalive: options.keepalive }).catch((err) => {
        if (!options.keepalive) setQueueStatus(err instanceof Error ? err.message : '观看进度同步失败');
      });
    },
    [manifest?.duration_ms],
  );

  useEffect(() => {
    const flush = () => {
      queueRef.current?.flush().catch((err) => setQueueStatus(err instanceof Error ? err.message : '互动事件上报失败'));
      syncWatchProgress({ force: true, keepalive: true });
    };
    const interval = window.setInterval(flush, 10000);
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') flush();
    };
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      syncWatchProgress({ force: true, keepalive: true });
      window.clearInterval(interval);
      window.removeEventListener('pagehide', flush);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [syncWatchProgress]);

  useEffect(() => {
    if (!manifest || !episode) return undefined;
    timelineRef.current?.pause();
    if (layerRef.current) clearInteraction(layerRef.current);
    videoRef.current?.pause();
    if (videoRef.current) videoRef.current.currentTime = 0;
    setIsPlaying(false);
    setCurrentMs(0);

    const timeline = new InteractionTimeline({
      manifest,
      onActivate: (point: InteractionPoint) => {
        const layer = layerRef.current;
        if (!layer) return;
        renderInteraction(layer, {
          interactionPoint: point,
          assetBaseUrl: manifest.client_hints?.asset_base_url || '/assets/',
          deviceTier: 'MEDIUM',
          statsSnapshot: null,
          onInteract: (event: { eventType: string; actionData: Record<string, unknown> }) => {
            queueRef.current?.enqueue({
              dramaId,
              episodeNumber,
              pointId: point.id,
              type: event.eventType,
              actionData: event.actionData,
              atMs: (videoRef.current?.currentTime || timeline.currentMs / 1000) * 1000,
            });
            queueRef.current?.flush().catch((err) => setQueueStatus(err instanceof Error ? err.message : '互动事件上报失败'));
            if (point.component !== 'emotion_buffer' || event.actionData.skip_forward_seconds !== 10) return;
            const video = videoRef.current;
            if (!video) return;
            const nextTime = Number.isFinite(video.duration) ? Math.min(video.duration, video.currentTime + 10) : video.currentTime + 10;
            video.currentTime = nextTime;
            timeline.seek(nextTime * 1000);
            setCurrentMs(nextTime * 1000);
          },
          onDismiss: (reason: string) => timeline.dismissActive(reason),
        });
      },
      onDismiss: () => {
        if (layerRef.current) clearInteraction(layerRef.current);
      },
      onTick: setCurrentMs,
    });

    timelineRef.current = timeline;

    return () => {
      timeline.pause();
      if (layerRef.current) clearInteraction(layerRef.current);
      syncWatchProgress({ force: true });
    };
  }, [dramaId, episode, episodeNumber, manifest, syncWatchProgress]);

  const togglePlayback = async () => {
    const video = videoRef.current;
    const timeline = timelineRef.current;
    if (!timeline) return;

    if (timeline.running) {
      syncWatchProgress({ force: true });
      timeline.pause();
      video?.pause();
      setIsPlaying(false);
      return;
    }

    timeline.play(Boolean(video));
    await video?.play().catch(() => undefined);
    setIsPlaying(true);
  };

  const seekTo = (ms: number) => {
    const video = videoRef.current;
    const timeline = timelineRef.current;
    if (!timeline) return;
    const nextMs = Math.min(ms, manifest?.duration_ms || ms);
    if (video) {
      video.currentTime = nextMs / 1000;
      timeline.seek(nextMs);
    } else {
      timeline.seek(nextMs);
    }
    setCurrentMs(nextMs);
    syncWatchProgress({ force: true, progressMs: nextMs, durationMs: manifest?.duration_ms || nextMs });
  };

  if (loading) return <LoadingState title="正在加载播放器" />;
  if (error || !episode || !manifest) return <ErrorState title="播放器不可用" message={error || '剧集数据不完整'} onAction={reload} />;

  return (
    <main className="phone-safe relative flex min-h-dvh flex-col bg-black">
      <header className="absolute left-0 right-0 top-0 z-40 flex h-14 items-center justify-between px-margin-page text-white">
        <Link className="icon-button bg-black/20 backdrop-blur" to="/home" aria-label="返回首页">
          <ChevronLeft size={28} />
        </Link>
        <div className="max-w-60 truncate rounded-full bg-black/25 px-3 py-1 text-label-md backdrop-blur">{manifest.title || episode.title}</div>
        <Link className="icon-button bg-black/20 backdrop-blur" to={`/detail?drama=${dramaId}`} aria-label="选集">
          <ListVideo size={21} />
        </Link>
      </header>

      <section className="relative flex flex-1 items-center justify-center overflow-hidden bg-black">
        <video
          ref={videoRef}
          className="h-auto w-full object-contain"
          src={manifest.video_url || episode.videoUrl}
          playsInline
          preload="metadata"
          onLoadedMetadata={(event) => {
            const duration = event.currentTarget.duration;
            if (Number.isFinite(duration) && duration > 0) {
              setManifest((current) => current ? { ...current, duration_ms: Math.round(duration * 1000) } : current);
            }
          }}
          onTimeUpdate={(event) => {
            const nextMs = event.currentTarget.currentTime * 1000;
            timelineRef.current?.sync(nextMs);
            setCurrentMs(nextMs);
            syncWatchProgress();
          }}
          onEnded={() => {
            syncWatchProgress({ force: true });
            timelineRef.current?.pause();
            setIsPlaying(false);
            if (episode.isLastEpisode && drama?.hasBranchNarrative) {
              setShowBranchPrompt(true);
            }
          }}
          onPause={() => syncWatchProgress({ force: true })}
        />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-black/80 to-transparent" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-black/80 to-transparent" />
        <div ref={layerRef} className="absolute inset-0 z-30 overflow-hidden touch-none" />
      </section>

      <section className="absolute bottom-0 left-0 right-0 z-40 px-margin-page pb-8 pt-20 text-white">
        <div className="mb-3 flex items-center justify-between">
          <div className="min-w-0">
            <p className="truncate text-label-md text-white/70">{episode.title}</p>
            <h1 className="truncate text-display-lg-mobile font-bold">{drama?.title || dramaId}</h1>
            {manifestStatus ? <p className="mt-1 text-label-md text-white/65">暂无互动配置：{manifestStatus}</p> : null}
            {queueStatus ? <p className="mt-1 text-label-md text-white/65">{queueStatus}</p> : null}
          </div>
          <button
            className="primary-gradient grid h-14 w-14 shrink-0 place-items-center rounded-full text-white shadow-xl transition active:scale-95"
            type="button"
            onClick={togglePlayback}
            aria-label={isPlaying ? '暂停' : '播放'}
          >
            {isPlaying ? <Pause size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" />}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <span className="w-11 text-label-md text-white/70">{formatTime(currentMs)}</span>
          <input
            className="h-1 flex-1 cursor-pointer appearance-none rounded-full border-0 bg-white/20 p-0 accent-primary"
            type="range"
            min={0}
            max={manifest.duration_ms || 1}
            value={Math.round(currentMs)}
            step={100}
            onChange={(event) => seekTo(Number(event.currentTarget.value))}
            style={{
              background: `linear-gradient(90deg, #d0bcff ${progress}%, rgba(255,255,255,.2) ${progress}%)`,
            }}
          />
          <span className="w-11 text-right text-label-md text-white/70">{formatTime(manifest.duration_ms)}</span>
        </div>
      </section>

      {/* Branch narrative prompt overlay */}
      {showBranchPrompt ? (
        <section className="absolute inset-0 z-50 flex items-end justify-center bg-gradient-to-t from-black/95 via-black/70 to-transparent px-margin-page pb-12">
          <div className="w-full max-w-sm animate-[fadeInUp_0.5s_ease-out] rounded-2xl border border-primary/30 bg-black/80 p-6 text-center backdrop-blur-2xl">
            <Sparkles size={36} className="mx-auto mb-3 text-primary" />
            <h2 className="mb-2 text-headline-md font-bold text-white">剧集已完结</h2>
            <p className="mb-2 text-body-sm text-white/60">
              AI 已为你生成三条不同的续写支线，选择你的命运走向，继续探索这个故事的更多可能。
            </p>
            <div className="mb-4 flex flex-wrap justify-center gap-1.5">
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-label-xs text-primary">多结局</span>
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-label-xs text-primary">互动叙事</span>
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-label-xs text-primary">AI 续写</span>
            </div>
            <div className="flex gap-3">
              <button
                className="flex-1 rounded-xl border border-white/15 bg-white/5 py-3 text-body-md text-white/70 backdrop-blur transition active:scale-95"
                type="button"
                onClick={() => setShowBranchPrompt(false)}
              >
                稍后再说
              </button>
              <Link
                className="primary-gradient flex flex-1 items-center justify-center gap-2 rounded-xl py-3 text-body-md font-semibold text-white transition active:scale-95"
                to={`/branch?drama=${dramaId}`}
              >
                <Sparkles size={18} />
                进入续写
              </Link>
            </div>
          </div>
        </section>
      ) : null}
    </main>
  );
}
