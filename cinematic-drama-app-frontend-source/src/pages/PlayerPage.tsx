import { ChevronLeft, ListVideo, Pause, Play, Sparkles } from 'lucide-react';
import { Capacitor } from '@capacitor/core';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorState, LoadingState } from '../components/PageState';
import { loadDrama, loadEpisodeManifest } from '../data/catalog';
import type { DramaItem, Episode } from '../data/catalog';
import { createEmptyManifest } from '../data/manifest';
import { updateWatchProgress } from '../data/profile';
import { clearInteraction, renderInteraction } from '../interaction/components.js';
import { LocalEventQueue } from '../interaction/queue';
import { InteractionTimeline } from '../interaction/timeline.js';
import type { InteractionManifest, InteractionPoint, InteractionTimeline as InteractionTimelineType } from '../interaction/types';

function formatTime(value: number) {
  if (!Number.isFinite(value) || value < 0) return '00:00';
  const totalSeconds = Math.floor(value / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return [hours, minutes, seconds].map((part) => String(part).padStart(2, '0')).join(':');
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export default function PlayerPage() {
  const [searchParams] = useSearchParams();
  const dramaId = searchParams.get('drama') || 'furao-dadi';
  const requestedEpisodeNumber = Number(searchParams.get('episode') || '1') || 1;
  const [drama, setDrama] = useState<DramaItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [manifests, setManifests] = useState<Record<number, InteractionManifest>>({});
  const [episodeDurations, setEpisodeDurations] = useState<Record<number, number>>({});
  const [manifestStatus, setManifestStatus] = useState<Record<number, string>>({});
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  const [progressMs, setProgressMs] = useState<number[]>([]);
  const [paused, setPaused] = useState<boolean[]>([]);
  const [showBranchPrompt, setShowBranchPrompt] = useState(false);
  const videoRefs = useRef<Array<HTMLVideoElement | null>>([]);
  const layerRefs = useRef<Array<HTMLDivElement | null>>([]);
  const timelineRef = useRef<InteractionTimelineType | null>(null);
  const queueRef = useRef<LocalEventQueue | null>(null);
  const manifestsRef = useRef<Record<number, InteractionManifest>>({});
  const activeIndexRef = useRef(0);
  const episodesRef = useRef<Episode[]>([]);
  const lastProgressSyncRef = useRef<Record<string, number>>({});
  const soundUnlockedRef = useRef(Capacitor.isNativePlatform());
  const initialScrollDoneRef = useRef(false);

  const episodes = useMemo(() => drama?.episodes || [], [drama]);

  useEffect(() => {
    activeIndexRef.current = activeIndex;
  }, [activeIndex]);

  useEffect(() => {
    episodesRef.current = episodes;
  }, [episodes]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    setManifestStatus({});
    setShowBranchPrompt(false);
    initialScrollDoneRef.current = false;
    try {
      const loadedDrama = await loadDrama(dramaId);
      if (!loadedDrama.episodes.length) throw new Error('后端暂无可播放剧集');
      const initialIndex = Math.max(0, loadedDrama.episodes.findIndex((item) => item.episodeNumber === requestedEpisodeNumber));
      setDrama(loadedDrama);
      setActiveIndex(initialIndex);
      setProgressMs(loadedDrama.episodes.map(() => 0));
      setPaused(loadedDrama.episodes.map(() => true));
      manifestsRef.current = {};
      setManifests({});
      setEpisodeDurations({});
    } catch (err) {
      setError(err instanceof Error ? err.message : '播放器加载失败');
    } finally {
      setLoading(false);
    }
  }, [dramaId, requestedEpisodeNumber]);

  useEffect(() => {
    queueRef.current = new LocalEventQueue(setQueueStatus);
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!episodes.length || initialScrollDoneRef.current) return;
    const node = videoRefs.current[activeIndex];
    if (!node) return;
    initialScrollDoneRef.current = true;
    node.closest('article')?.scrollIntoView({ block: 'start' });
  }, [activeIndex, episodes.length]);

  const getManifest = (episode: Episode) => manifests[episode.episodeNumber] || createEmptyManifest(dramaId, episode);

  const getVideoDurationMs = (video: HTMLVideoElement | null, episode?: Episode) => {
    if (video && Number.isFinite(video.duration) && video.duration > 0) return Math.round(video.duration * 1000);
    if (episode) return manifests[episode.episodeNumber]?.duration_ms || episodeDurations[episode.episodeNumber] || 0;
    return 0;
  };

  const syncWatchProgress = useCallback(
    (episode: Episode | null | undefined, video: HTMLVideoElement | null, options: { force?: boolean; keepalive?: boolean } = {}) => {
      if (!episode || !video) return;
      const currentTime = Number.isFinite(video.currentTime) && video.currentTime > 0 ? video.currentTime : 0;
      const durationMs = video && Number.isFinite(video.duration) && video.duration > 0
        ? Math.round(video.duration * 1000)
        : manifestsRef.current[episode.episodeNumber]?.duration_ms || 0;
      const nextProgressMs = Math.max(0, Math.round(currentTime * 1000));
      if (!durationMs && !nextProgressMs) return;

      const now = Date.now();
      const previous = lastProgressSyncRef.current[episode.id] || 0;
      if (!options.force && now - previous < 5000) return;
      lastProgressSyncRef.current[episode.id] = now;

      updateWatchProgress(episode.id, nextProgressMs, durationMs || nextProgressMs, { keepalive: options.keepalive }).catch((err) => {
        if (!options.keepalive) setQueueStatus(err instanceof Error ? err.message : '观看进度同步失败');
      });
    },
    [],
  );

  useEffect(() => {
    const syncCurrentProgress = (keepalive = false) => {
      const index = activeIndexRef.current;
      syncWatchProgress(episodesRef.current[index], videoRefs.current[index], { force: true, keepalive });
    };
    const flush = () => {
      queueRef.current?.flush().catch((err) => setQueueStatus(err instanceof Error ? err.message : '互动事件上报失败'));
      syncCurrentProgress(true);
    };
    const interval = window.setInterval(flush, 10000);
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') flush();
    };
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      flush();
      window.clearInterval(interval);
      window.removeEventListener('pagehide', flush);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [syncWatchProgress]);

  const playVideo = async (video: HTMLVideoElement | null, options: { withSound?: boolean } = {}) => {
    if (!video) return false;
    video.playsInline = true;
    video.muted = !options.withSound;
    try {
      await video.play();
      return true;
    } catch {
      if (!options.withSound) return false;
      video.muted = true;
      try {
        await video.play();
        return true;
      } catch {
        return false;
      }
    }
  };

  const activateVideo = useCallback((index: number) => {
    videoRefs.current.forEach((video, itemIndex) => {
      if (!video) return;
      if (itemIndex !== index) {
        video.pause();
        video.muted = true;
        return;
      }
      void playVideo(video, { withSound: soundUnlockedRef.current });
    });
  }, []);

  const handleFeedScroll = useCallback((event: React.UIEvent<HTMLElement>) => {
    const feed = event.currentTarget;
    if (feed.clientHeight <= 0 || !episodes.length) return;
    const nextIndex = Math.max(0, Math.min(episodes.length - 1, Math.round(feed.scrollTop / feed.clientHeight)));
    if (nextIndex === activeIndexRef.current) return;
    activeIndexRef.current = nextIndex;
    activateVideo(nextIndex);
    setActiveIndex(nextIndex);
  }, [activateVideo, episodes.length]);

  useEffect(() => {
    if (!episodes.length) return;
    activateVideo(activeIndex);
  }, [activeIndex, activateVideo, episodes.length]);

  const togglePlaybackAt = async (index: number) => {
    const video = videoRefs.current[index];
    if (!video) return;
    soundUnlockedRef.current = true;
    video.muted = false;
    if (video.paused) {
      const played = await playVideo(video, { withSound: true });
      if (played) setPaused((current) => current.map((value, itemIndex) => (itemIndex === index ? false : value)));
      return;
    }
    video.pause();
  };

  const updateManifestDuration = (episode: Episode, durationMs: number) => {
    if (!durationMs) return;
    setEpisodeDurations((current) => (
      current[episode.episodeNumber] === durationMs
        ? current
        : { ...current, [episode.episodeNumber]: durationMs }
    ));
    setManifests((current) => {
      const existing = current[episode.episodeNumber];
      if (!existing) return current;
      if (existing.duration_ms === durationMs) return current;
      const next = {
        ...current,
        [episode.episodeNumber]: { ...existing, duration_ms: durationMs },
      };
      manifestsRef.current = next;
      return next;
    });
    if (timelineRef.current && episodesRef.current[activeIndexRef.current]?.id === episode.id) {
      timelineRef.current.manifest.duration_ms = durationMs;
    }
  };

  const enqueueEvent = (episode: Episode, pointId: string, type: string, actionData: Record<string, unknown>, atMs = 0) => {
    queueRef.current?.enqueue({
      dramaId,
      episodeNumber: episode.episodeNumber,
      pointId,
      type,
      actionData,
      atMs,
    });
    queueRef.current?.flush().catch((err) => setQueueStatus(err instanceof Error ? err.message : '互动事件上报失败'));
  };

  useEffect(() => {
    if (!episodes.length) return undefined;
    const timelineIndex = activeIndex;
    const episode = episodes[timelineIndex];
    if (!episode) return undefined;
    let disposed = false;

    async function activate() {
      setShowBranchPrompt(false);
      timelineRef.current?.pause();
      layerRefs.current.forEach((layer) => layer && clearInteraction(layer));
      activateVideo(timelineIndex);

      let manifest: InteractionManifest | null | undefined = manifestsRef.current[episode.episodeNumber];
      if (!manifest) {
        manifest = await loadEpisodeManifest(dramaId, episode.episodeNumber).catch((err) => {
          setManifestStatus((current) => ({
            ...current,
            [episode.episodeNumber]: err instanceof Error ? err.message : '互动配置加载失败',
          }));
          return null;
        });
        if (disposed || !manifest || activeIndexRef.current !== timelineIndex) return;
        const loadedManifest = manifest;
        setManifests((current) => {
          const next = { ...current, [episode.episodeNumber]: loadedManifest };
          manifestsRef.current = next;
          return next;
        });
      }
      if (!manifest || disposed || activeIndexRef.current !== timelineIndex) return;

      const video = videoRefs.current[timelineIndex];
      const durationMs = getVideoDurationMs(video, episode);
      const timelineManifest = {
        ...manifest,
        duration_ms: durationMs || manifest.duration_ms,
      } as InteractionManifest;

      const timeline = new InteractionTimeline({
        manifest: timelineManifest,
        onActivate: (point: InteractionPoint) => {
          if (activeIndexRef.current !== timelineIndex) return;
          const layer = layerRefs.current[timelineIndex];
          if (!layer) return;
          layer.style.zIndex = '90';
          renderInteraction(layer, {
            interactionPoint: point,
            assetBaseUrl: timelineManifest.client_hints?.asset_base_url || '/assets/',
            deviceTier: 'MEDIUM',
            statsSnapshot: null,
            onInteract: (event: { eventType: string; actionData: Record<string, unknown> }) => {
              enqueueEvent(episode, point.id, event.eventType, event.actionData, (videoRefs.current[timelineIndex]?.currentTime || 0) * 1000);
              if (point.component !== 'emotion_buffer' || event.actionData.skip_forward_seconds !== 10) return;
              const currentVideo = videoRefs.current[timelineIndex];
              if (!currentVideo) return;
              const nextTime = Number.isFinite(currentVideo.duration)
                ? Math.min(currentVideo.duration, currentVideo.currentTime + 10)
                : currentVideo.currentTime + 10;
              currentVideo.currentTime = nextTime;
              timeline.seek(nextTime * 1000);
              setProgressMs((current) => current.map((value, index) => (index === timelineIndex ? nextTime * 1000 : value)));
            },
            onDismiss: (reason: string) => timeline.dismissActive(reason),
          });
        },
        onDismiss: () => {
          const layer = layerRefs.current[timelineIndex];
          if (layer) {
            clearInteraction(layer);
            layer.style.zIndex = '90';
          }
        },
        onTick: () => undefined,
      });
      timelineRef.current = timeline;
      timeline.play(true);
      timeline.sync((videoRefs.current[timelineIndex]?.currentTime || 0) * 1000);
    }

    void activate();
    return () => {
      disposed = true;
      syncWatchProgress(episode, videoRefs.current[timelineIndex], { force: true });
      timelineRef.current?.pause();
      const layer = layerRefs.current[timelineIndex];
      if (layer) {
        clearInteraction(layer);
        layer.style.zIndex = '90';
      }
    };
  }, [activeIndex, activateVideo, dramaId, episodes, syncWatchProgress]);

  if (loading) return <LoadingState title="正在加载播放器" />;
  if (error || !drama || !episodes.length) return <ErrorState title="播放器不可用" message={error || '剧集数据不完整'} onAction={reload} />;

  return (
    <main className="phone-safe relative h-dvh overflow-hidden bg-black">
      <header className="pointer-events-none absolute left-0 right-0 top-0 z-40 flex h-14 items-center justify-between px-margin-page text-white">
        <Link className="pointer-events-auto icon-button bg-black/20 backdrop-blur" to="/home" aria-label="返回首页">
          <ChevronLeft size={28} />
        </Link>
        <div className="max-w-60 truncate rounded-full bg-black/25 px-3 py-1 text-label-md backdrop-blur">
          第 {episodes[activeIndex]?.episodeNumber || requestedEpisodeNumber} 集
        </div>
        <Link className="pointer-events-auto icon-button bg-black/20 backdrop-blur" to={`/detail?drama=${dramaId}`} aria-label="选集">
          <ListVideo size={21} />
        </Link>
      </header>

      <section className="h-full snap-y snap-mandatory overflow-y-auto scroll-smooth" onScroll={handleFeedScroll}>
        {episodes.map((episode, index) => {
          const manifest = getManifest(episode);
          const durationMs = getVideoDurationMs(videoRefs.current[index], episode);
          const currentProgressMs = progressMs[index] || 0;
          const progress = durationMs ? Math.min(100, Math.max(0, (currentProgressMs / durationMs) * 100)) : 0;
          return (
            <article
              key={episode.id}
              className="relative h-dvh snap-start overflow-hidden bg-black"
              onClick={(event) => {
                if ((event.target as HTMLElement).closest('[data-video-control]')) return;
                void togglePlaybackAt(index);
              }}
            >
              <video
                ref={(node) => {
                  videoRefs.current[index] = node;
                }}
                data-index={index}
                className="absolute inset-x-0 top-1/2 h-auto w-full -translate-y-1/2 object-contain"
                src={manifest.video_url || episode.videoUrl}
                muted={!soundUnlockedRef.current || index !== activeIndex}
                playsInline
                preload={Math.abs(index - activeIndex) <= 1 ? 'auto' : 'metadata'}
                onLoadedMetadata={(event) => {
                  updateManifestDuration(episode, getVideoDurationMs(event.currentTarget, episode));
                  if (index === activeIndexRef.current) activateVideo(index);
                }}
                onCanPlay={() => {
                  if (index === activeIndexRef.current && videoRefs.current[index]?.paused) activateVideo(index);
                }}
                onTimeUpdate={(event) => {
                  const nextMs = event.currentTarget.currentTime * 1000;
                  setProgressMs((current) => current.map((value, itemIndex) => (itemIndex === index ? nextMs : value)));
                  syncWatchProgress(episode, event.currentTarget);
                  if (index === activeIndex) timelineRef.current?.sync(nextMs);
                }}
                onPlay={() => setPaused((current) => current.map((value, itemIndex) => (itemIndex === index ? false : value)))}
                onPause={(event) => {
                  setPaused((current) => current.map((value, itemIndex) => (itemIndex === index ? true : value)));
                  syncWatchProgress(episode, event.currentTarget, { force: true });
                }}
                onEnded={(event) => {
                  syncWatchProgress(episode, event.currentTarget, { force: true });
                  timelineRef.current?.pause();
                  setPaused((current) => current.map((value, itemIndex) => (itemIndex === index ? true : value)));
                  if (episode.isLastEpisode && drama.hasBranchNarrative) setShowBranchPrompt(true);
                  else event.currentTarget.closest('article')?.nextElementSibling?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }}
              />

              <div data-video-control ref={(node) => { layerRefs.current[index] = node; }} className="pointer-events-none absolute inset-0 z-[90] overflow-hidden" />
              <div className="pointer-events-none absolute inset-x-0 top-0 h-36 bg-gradient-to-b from-black/80 to-transparent" />
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-72 bg-gradient-to-t from-black via-black/55 to-transparent" />

              <button
                data-video-control
                className={`absolute left-1/2 top-1/2 z-40 grid h-[54px] w-[54px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-neutral-900/55 text-white/90 transition-opacity duration-200 ${
                  paused[index] ? 'opacity-100' : 'pointer-events-none opacity-0'
                }`}
                type="button"
                aria-label={paused[index] ? '播放' : '暂停'}
                onClick={(event) => {
                  event.stopPropagation();
                  void togglePlaybackAt(index);
                }}
              >
                {paused[index] ? <Play size={26} fill="currentColor" className="translate-x-0.5" /> : <Pause size={25} fill="currentColor" />}
              </button>

              <section className="pointer-events-none absolute bottom-20 left-0 right-0 z-40 px-margin-page text-white">
                <p className="mb-1 text-label-md text-primary">{drama.title} · 第 {episode.episodeNumber} 集</p>
                <h1 className="mb-2 line-clamp-2 text-display-lg-mobile font-bold">{episode.title}</h1>
                <p className="line-clamp-2 text-body-sm text-white/75">{drama.description}</p>
                {manifestStatus[episode.episodeNumber] ? (
                  <p className="mt-2 text-label-md text-white/65">暂无互动配置，视频可继续播放</p>
                ) : null}
                {queueStatus && index === activeIndex ? <p className="mt-2 text-label-md text-white/65">{queueStatus}</p> : null}
              </section>

              <div data-video-control className="absolute inset-x-0 bottom-14 z-50 px-margin-page">
                <div className="mb-2 flex items-center justify-between text-label-md text-white/70">
                  <span>{formatTime(currentProgressMs)}</span>
                  <span>{formatTime(durationMs)}</span>
                </div>
                <input
                  className="h-1 w-full cursor-pointer appearance-none rounded-full border-0 bg-white/20 p-0 accent-primary"
                  type="range"
                  min={0}
                  max={durationMs || 1}
                  value={Math.min(Math.round(currentProgressMs), durationMs || 1)}
                  step={100}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(event) => {
                    const video = videoRefs.current[index];
                    const nextMs = Number(event.currentTarget.value);
                    if (video) video.currentTime = nextMs / 1000;
                    if (index === activeIndex) timelineRef.current?.seek(nextMs);
                    setProgressMs((current) => current.map((value, itemIndex) => (itemIndex === index ? nextMs : value)));
                    syncWatchProgress(episode, videoRefs.current[index], { force: true });
                  }}
                  style={{
                    background: `linear-gradient(90deg, #d0bcff ${progress}%, rgba(255,255,255,.2) ${progress}%)`,
                  }}
                />
              </div>
            </article>
          );
        })}
      </section>

      {showBranchPrompt ? (
        <section className="absolute inset-0 z-50 flex items-end justify-center bg-gradient-to-t from-black/95 via-black/70 to-transparent px-margin-page pb-12">
          <div className="w-full max-w-sm rounded-2xl border border-primary/30 bg-black/80 p-6 text-center backdrop-blur-2xl">
            <Sparkles size={36} className="mx-auto mb-3 text-primary" />
            <h2 className="mb-2 text-headline-md font-bold text-white">剧集已完结</h2>
            <p className="mb-4 text-body-sm text-white/60">AI 已为你生成不同的续写支线，可以继续探索故事的更多可能。</p>
            <div className="flex gap-3">
              <button
                className="flex-1 rounded-xl border border-white/15 bg-white/5 py-3 text-body-md text-white/70"
                type="button"
                onClick={() => setShowBranchPrompt(false)}
              >
                稍后再说
              </button>
              <Link
                className="primary-gradient flex flex-1 items-center justify-center gap-2 rounded-xl py-3 text-body-md font-semibold text-white"
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
