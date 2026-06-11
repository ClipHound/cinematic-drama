import { Bot, Heart, MessageCircle, Play, Search } from 'lucide-react';
import { Capacitor } from '@capacitor/core';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { EmptyState, ErrorState, LoadingState } from '../components/PageState';
import { loadDramas, loadEpisodeManifest } from '../data/catalog';
import type { DramaItem, Episode } from '../data/catalog';
import { updateWatchProgress } from '../data/profile';
import { loadComments, loadFavorites, postComment, setFavorite } from '../data/social';
import type { CommentItem } from '../data/social';
import { clearInteraction, renderInteraction } from '../interaction/components.js';
import { LocalEventQueue } from '../interaction/queue';
import { InteractionTimeline } from '../interaction/timeline.js';
import type { InteractionManifest, InteractionPoint, InteractionTimeline as InteractionTimelineType } from '../interaction/types';

function formatTime(value: number) {
  if (!Number.isFinite(value) || value < 0) return '00:00';
  const totalSeconds = Math.floor(value);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return [hours, minutes, seconds].map((part) => String(part).padStart(2, '0')).join(':');
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export default function HomePage() {
  const [drama, setDrama] = useState<DramaItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [progress, setProgress] = useState<number[]>([]);
  const [paused, setPaused] = useState<boolean[]>([]);
  const [liked, setLiked] = useState<Record<string, boolean>>({});
  const [commentEpisode, setCommentEpisode] = useState<Episode | null>(null);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [commentInput, setCommentInput] = useState('');
  const [commentError, setCommentError] = useState<string | null>(null);
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [seekPreview, setSeekPreview] = useState<{ index: number; time: number; ratio: number } | null>(null);
  const [interactionActive, setInteractionActive] = useState<boolean[]>([]);
  const videoRefs = useRef<Array<HTMLVideoElement | null>>([]);
  const layerRefs = useRef<Array<HTMLDivElement | null>>([]);
  const timelineRef = useRef<InteractionTimelineType | null>(null);
  const queueRef = useRef<LocalEventQueue | null>(null);
  const draggingIndexRef = useRef<number | null>(null);
  const activePointerIdRef = useRef<number | null>(null);
  const pointerStartXRef = useRef(0);
  const pointerMovedRef = useRef(false);
  const previewTimerRef = useRef<number | null>(null);
  const activeIndexRef = useRef(0);
  const feedEpisodesRef = useRef<Episode[]>([]);
  const lastProgressSyncRef = useRef<Record<string, number>>({});
  const soundUnlockedRef = useRef(Capacitor.isNativePlatform());

  const feedEpisodes = useMemo(() => drama?.episodes || [], [drama]);

  useEffect(() => {
    activeIndexRef.current = activeIndex;
  }, [activeIndex]);

  useEffect(() => {
    feedEpisodesRef.current = feedEpisodes;
  }, [feedEpisodes]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const dramas = await loadDramas();
      const selected = dramas.find((item) => item.episodes.length > 0) || dramas[0] || null;
      if (!selected) throw new Error('后端暂无可播放剧目');
      setDrama(selected);
      setActiveIndex(0);
      setProgress(selected.episodes.map(() => 0));
      setPaused(selected.episodes.map(() => true));
      setInteractionActive(selected.episodes.map(() => false));
      const favorites = await loadFavorites().catch(() => new Set<string>());
      setLiked({ [selected.id]: favorites.has(selected.id) });
    } catch (err) {
      setError(err instanceof Error ? err.message : '首页数据加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueRef.current = new LocalEventQueue(setQueueStatus);
    void reload();
    const flush = () => {
      queueRef.current?.flush().catch((err) => setQueueStatus(err instanceof Error ? err.message : '互动事件上报失败'));
    };
    const interval = window.setInterval(flush, 10000);
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') flush();
    };
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('pagehide', flush);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [reload]);

  useEffect(() => () => {
    if (previewTimerRef.current !== null) window.clearTimeout(previewTimerRef.current);
  }, []);

  const getVideoProgress = (video: HTMLVideoElement | null) => {
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return 0;
    return Math.max(0, Math.min(1, video.currentTime / video.duration));
  };

  const setProgressAtIndex = (index: number, nextProgress: number) => {
    setProgress((current) => current.map((value, itemIndex) => (itemIndex === index ? nextProgress : value)));
  };

  const updateProgress = (index: number, video: HTMLVideoElement) => {
    setProgressAtIndex(index, getVideoProgress(video));
  };

  const getVideoDurationMs = (video: HTMLVideoElement | null) => {
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return 0;
    return Math.round(video.duration * 1000);
  };

  const syncTimelineDuration = (video: HTMLVideoElement | null, index = activeIndex) => {
    const durationMs = getVideoDurationMs(video);
    if (durationMs > 0 && index === activeIndex && timelineRef.current) timelineRef.current.manifest.duration_ms = durationMs;
    return durationMs;
  };

  const syncWatchProgress = useCallback(
    (episode: Episode | null | undefined, video: HTMLVideoElement | null, options: { force?: boolean; keepalive?: boolean } = {}) => {
      if (!episode || !video) return;
      const currentTime = Number.isFinite(video.currentTime) && video.currentTime > 0 ? video.currentTime : 0;
      const durationMs = getVideoDurationMs(video);
      const progressMs = Math.max(0, Math.round(currentTime * 1000));
      if (!durationMs && !progressMs) return;

      const now = Date.now();
      const previous = lastProgressSyncRef.current[episode.id] || 0;
      if (!options.force && now - previous < 5000) return;
      lastProgressSyncRef.current[episode.id] = now;

      updateWatchProgress(episode.id, progressMs, durationMs || progressMs, { keepalive: options.keepalive }).catch((err) => {
        if (!options.keepalive) setQueueStatus(err instanceof Error ? err.message : '观看进度同步失败');
      });
    },
    [],
  );

  useEffect(() => {
    const syncCurrentProgress = (keepalive = false) => {
      const index = activeIndexRef.current;
      syncWatchProgress(feedEpisodesRef.current[index], videoRefs.current[index], { force: true, keepalive });
    };
    const onPageHide = () => syncCurrentProgress(true);
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') syncCurrentProgress(true);
    };
    window.addEventListener('pagehide', onPageHide);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      syncCurrentProgress(true);
      window.removeEventListener('pagehide', onPageHide);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [syncWatchProgress]);

  useEffect(() => {
    return () => {
      syncWatchProgress(feedEpisodes[activeIndex], videoRefs.current[activeIndex], { force: true });
    };
  }, [activeIndex, feedEpisodes, syncWatchProgress]);

  const enqueueEvent = (episode: Episode, pointId: string, type: string, actionData: Record<string, unknown>, atMs = 0) => {
    if (!drama) return;
    queueRef.current?.enqueue({
      dramaId: drama.id,
      episodeNumber: episode.episodeNumber,
      pointId,
      type,
      actionData,
      atMs,
    });
    queueRef.current?.flush().catch((err) => setQueueStatus(err instanceof Error ? err.message : '互动事件上报失败'));
  };

  const toggleFavorite = async (episode: Episode, index: number) => {
    if (!drama) return;
    const nextValue = !liked[drama.id];
    setLiked((current) => ({ ...current, [drama.id]: nextValue }));
    try {
      await setFavorite(drama.id, nextValue);
      enqueueEvent(episode, 'feed-like', 'like', { liked: nextValue }, (videoRefs.current[index]?.currentTime || 0) * 1000);
    } catch (err) {
      setLiked((current) => ({ ...current, [drama.id]: !nextValue }));
      setQueueStatus(err instanceof Error ? err.message : '收藏状态更新失败');
    }
  };

  const openComments = async (episode: Episode, index: number) => {
    if (!drama) return;
    setCommentEpisode(episode);
    setCommentError(null);
    setComments([]);
    enqueueEvent(episode, 'feed-comment', 'comment_open', {}, (videoRefs.current[index]?.currentTime || 0) * 1000);
    try {
      setComments(await loadComments(drama.id, episode.episodeNumber));
    } catch (err) {
      setCommentError(err instanceof Error ? err.message : '评论加载失败');
    }
  };

  const submitComment = async () => {
    if (!drama || !commentEpisode) return;
    const value = commentInput.trim();
    if (!value) return;
    setCommentError(null);
    try {
      await postComment(drama.id, commentEpisode.episodeNumber, value);
      setCommentInput('');
      setComments(await loadComments(drama.id, commentEpisode.episodeNumber));
    } catch (err) {
      setCommentError(err instanceof Error ? err.message : '评论发送失败');
    }
  };

  const seekFromPointer = (index: number, event: React.PointerEvent<HTMLDivElement>) => {
    const video = videoRefs.current[index];
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return null;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (bounds.width <= 0) return null;
    const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const time = ratio * video.duration;
    syncTimelineDuration(video, index);
    video.currentTime = time;
    const currentTime = Number.isFinite(video.currentTime) ? video.currentTime : time;
    const currentRatio = getVideoProgress(video);
    if (index === activeIndex) timelineRef.current?.seek(currentTime * 1000);
    setProgressAtIndex(index, currentRatio);
    setSeekPreview({ index, time: currentTime, ratio: currentRatio });
    return { time: currentTime, ratio: currentRatio };
  };

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
    if (feed.clientHeight <= 0 || !feedEpisodes.length) return;
    const nextIndex = Math.max(0, Math.min(feedEpisodes.length - 1, Math.round(feed.scrollTop / feed.clientHeight)));
    if (nextIndex === activeIndexRef.current) return;
    activeIndexRef.current = nextIndex;
    activateVideo(nextIndex);
    setActiveIndex(nextIndex);
  }, [activateVideo, feedEpisodes.length]);

  useEffect(() => {
    if (!feedEpisodes.length) return;
    activateVideo(activeIndex);
  }, [activeIndex, activateVideo, feedEpisodes.length]);

  const togglePlaybackAt = async (index: number) => {
    const video = videoRefs.current[index];
    if (!video) return;
    soundUnlockedRef.current = true;
    video.muted = false;
    if (video.paused) {
      const played = await playVideo(video, { withSound: true });
      if (played) {
        setPaused((current) => current.map((value, itemIndex) => (itemIndex === index ? false : value)));
      }
      return;
    }
    video.pause();
  };

  useEffect(() => {
    if (!drama || !feedEpisodes.length) return undefined;
    const currentDrama = drama;
    let disposed = false;
    const timelineIndex = activeIndex;
    const episode = feedEpisodes[timelineIndex];
    if (!episode) return undefined;

    async function activate() {
      timelineRef.current?.pause();
      layerRefs.current.forEach((layer) => layer && clearInteraction(layer));
      setInteractionActive((current) => current.map(() => false));

      activateVideo(timelineIndex);

      const manifest = await loadEpisodeManifest(currentDrama.id, episode.episodeNumber).catch(() => null);
      if (disposed || !manifest || activeIndexRef.current !== timelineIndex) return;
      const durationMs = getVideoDurationMs(videoRefs.current[timelineIndex]);
      const manifestWithDuration = {
        ...manifest,
        duration_ms: durationMs || manifest.duration_ms,
      } as InteractionManifest;

      const timeline = new InteractionTimeline({
        manifest: manifestWithDuration,
        onActivate: (point: InteractionPoint) => {
          if (activeIndexRef.current !== timelineIndex) return;
          const layer = layerRefs.current[timelineIndex];
          if (!layer) return;
          setInteractionActive((current) => current.map((value, index) => (index === timelineIndex ? true : value)));
          renderInteraction(layer, {
            interactionPoint: point,
            assetBaseUrl: manifestWithDuration.client_hints?.asset_base_url || '/assets/',
            deviceTier: 'MEDIUM',
            statsSnapshot: null,
            onInteract: (event: { eventType: string; actionData: Record<string, unknown> }) => {
              enqueueEvent(episode, point.id, event.eventType, event.actionData, (videoRefs.current[timelineIndex]?.currentTime || 0) * 1000);
              if (point.component !== 'emotion_buffer' || event.actionData.skip_forward_seconds !== 10) return;
              const video = videoRefs.current[timelineIndex];
              if (!video) return;
              const nextTime = Number.isFinite(video.duration) ? Math.min(video.duration, video.currentTime + 10) : video.currentTime + 10;
              syncTimelineDuration(video, timelineIndex);
              video.currentTime = nextTime;
              timeline.seek(nextTime * 1000);
              updateProgress(timelineIndex, video);
            },
            onDismiss: (reason: string) => timeline.dismissActive(reason),
          });
        },
        onDismiss: () => {
          const layer = layerRefs.current[timelineIndex];
          if (layer) clearInteraction(layer);
          setInteractionActive((current) => current.map((value, index) => (index === timelineIndex ? false : value)));
        },
        onTick: () => undefined,
      });
      timelineRef.current = timeline;
      timeline.play(true);
      timeline.sync((videoRefs.current[timelineIndex]?.currentTime || 0) * 1000);
    }

    activate();
    return () => {
      disposed = true;
      timelineRef.current?.pause();
    };
  }, [activeIndex, activateVideo, drama, feedEpisodes]);

  if (loading) return <LoadingState title="正在加载首页剧集" />;
  if (error) return <ErrorState title="首页不可用" message={error} onAction={reload} />;
  if (!drama || !feedEpisodes.length) {
    return (
      <main className="phone-safe min-h-dvh px-margin-page py-stack-lg">
        <EmptyState title="暂无可播放剧集" message="后端返回的剧目列表为空，或剧目还没有完成上架。" />
        <BottomNav />
      </main>
    );
  }

  return (
    <main className="phone-safe relative h-dvh overflow-hidden bg-black">
      <header className="pointer-events-none absolute left-0 right-0 top-0 z-40 flex h-14 items-center justify-between px-margin-page text-white">
        <strong className="text-headline-md drop-shadow-lg">首页</strong>
        <div className="pointer-events-auto flex gap-2">
          <Link className="grid h-9 w-9 place-items-center rounded-full bg-black/25 backdrop-blur" to="/search" aria-label="搜索">
            <Search size={18} />
          </Link>
          <Link className="grid h-9 w-9 place-items-center rounded-full bg-black/25 backdrop-blur" to="/ai" aria-label="AI 搜索">
            <Bot size={18} />
          </Link>
        </div>
      </header>

      <section className="h-full snap-y snap-mandatory overflow-y-auto scroll-smooth" onScroll={handleFeedScroll}>
        {feedEpisodes.map((episode, index) => (
          <article
            key={episode.id}
            className="relative h-dvh snap-start snap-always overflow-hidden bg-black"
            onClick={(event) => {
              if (interactionActive[index]) return;
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
              src={episode.videoUrl}
              muted={!soundUnlockedRef.current || index !== activeIndex}
              loop
              playsInline
              preload={index < 2 ? 'auto' : 'metadata'}
              onTimeUpdate={(event) => {
                if (draggingIndexRef.current === index) return;
                updateProgress(index, event.currentTarget);
                syncWatchProgress(episode, event.currentTarget);
                if (index === activeIndex) timelineRef.current?.sync(event.currentTarget.currentTime * 1000);
              }}
              onLoadedMetadata={(event) => {
                syncTimelineDuration(event.currentTarget, index);
                updateProgress(index, event.currentTarget);
                if (index === activeIndexRef.current) activateVideo(index);
              }}
              onCanPlay={() => {
                if (index === activeIndexRef.current && videoRefs.current[index]?.paused) activateVideo(index);
              }}
              onSeeking={(event) => {
                if (draggingIndexRef.current !== index) updateProgress(index, event.currentTarget);
              }}
              onSeeked={(event) => {
                if (draggingIndexRef.current !== index) updateProgress(index, event.currentTarget);
              }}
              onPlay={() => setPaused((current) => current.map((value, itemIndex) => (itemIndex === index ? false : value)))}
              onPause={(event) => {
                setPaused((current) => current.map((value, itemIndex) => (itemIndex === index ? true : value)));
                syncWatchProgress(episode, event.currentTarget, { force: true });
              }}
            />
            <div data-video-control ref={(node) => { layerRefs.current[index] = node; }} className="pointer-events-none absolute inset-0 z-[90] overflow-hidden" />
            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 h-72 bg-gradient-to-t from-black via-black/55 to-transparent" />

            <button
              data-video-control
              type="button"
              aria-label="继续播放"
              className={`absolute left-1/2 top-1/2 z-[44] grid h-[50px] w-[50px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-neutral-900/55 text-white/90 transition-opacity duration-200 ${
                paused[index] && !interactionActive[index] ? 'opacity-100' : 'pointer-events-none opacity-0'
              }`}
              onClick={(event) => {
                event.stopPropagation();
                void togglePlaybackAt(index);
              }}
            >
              <Play size={25} fill="currentColor" className="translate-x-0.5" />
            </button>

            <aside
              data-video-control
              className="absolute bottom-32 right-3 z-[80] flex flex-col items-center gap-5 text-white"
              onClick={(event) => event.stopPropagation()}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <button
                className={`pointer-events-auto grid h-11 w-11 place-items-center rounded-full backdrop-blur ${liked[drama.id] ? 'bg-primary-container text-white' : 'bg-black/25'}`}
                type="button"
                aria-label="喜欢"
                onClick={(event) => {
                  event.stopPropagation();
                  void toggleFavorite(episode, index);
                }}
              >
                <Heart size={23} fill={liked[drama.id] ? 'currentColor' : 'none'} />
              </button>
              <button
                className="pointer-events-auto grid h-11 w-11 place-items-center rounded-full bg-black/25 backdrop-blur"
                type="button"
                aria-label="评论"
                onClick={(event) => {
                  event.stopPropagation();
                  void openComments(episode, index);
                }}
              >
                <MessageCircle size={23} />
              </button>
            </aside>

            <section className="pointer-events-none absolute bottom-24 left-0 right-24 z-40 px-margin-page text-white">
              <p className="mb-1 text-label-md text-primary">{drama.title} · {episode.title}</p>
              <h2 className="mb-2 text-display-lg-mobile font-bold">
                <Link data-video-control className="pointer-events-auto inline-block" to={`/detail?drama=${drama.id}`}>
                  {drama.title}
                </Link>
              </h2>
              <p className="line-clamp-2 text-body-sm text-white/78">{drama.description}</p>
              {queueStatus ? <p className="mt-2 text-label-md text-white/70">{queueStatus}</p> : null}
            </section>

            <div
              data-video-control
              className="absolute inset-x-0 bottom-20 z-[60] flex h-2.5 touch-none cursor-pointer items-center"
              role="slider"
              aria-label={`${episode.title}播放进度`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round((progress[index] || 0) * 100)}
              tabIndex={0}
              onPointerDown={(event) => {
                event.preventDefault();
                event.stopPropagation();
                if (previewTimerRef.current !== null) window.clearTimeout(previewTimerRef.current);
                pointerStartXRef.current = event.clientX;
                pointerMovedRef.current = false;
                draggingIndexRef.current = index;
                activePointerIdRef.current = event.pointerId;
                event.currentTarget.setPointerCapture(event.pointerId);
                setDraggingIndex(index);
                seekFromPointer(index, event);
              }}
              onPointerMove={(event) => {
                if (draggingIndexRef.current !== index || activePointerIdRef.current !== event.pointerId) return;
                event.preventDefault();
                event.stopPropagation();
                if (Math.abs(event.clientX - pointerStartXRef.current) > 3) pointerMovedRef.current = true;
                seekFromPointer(index, event);
              }}
              onPointerUp={(event) => {
                if (draggingIndexRef.current !== index || activePointerIdRef.current !== event.pointerId) return;
                event.preventDefault();
                event.stopPropagation();
                seekFromPointer(index, event);
                if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                  event.currentTarget.releasePointerCapture(event.pointerId);
                }
                draggingIndexRef.current = null;
                activePointerIdRef.current = null;
                setDraggingIndex(null);
                if (pointerMovedRef.current) setSeekPreview(null);
                else previewTimerRef.current = window.setTimeout(() => setSeekPreview(null), 500);
                syncWatchProgress(episode, videoRefs.current[index], { force: true });
              }}
              onPointerCancel={() => {
                draggingIndexRef.current = null;
                activePointerIdRef.current = null;
                setDraggingIndex(null);
                setSeekPreview(null);
              }}
              onKeyDown={(event) => {
                const video = videoRefs.current[index];
                if (!video || !Number.isFinite(video.duration)) return;
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                event.preventDefault();
                syncTimelineDuration(video, index);
                video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + (event.key === 'ArrowRight' ? 5 : -5)));
                timelineRef.current?.seek(video.currentTime * 1000);
                updateProgress(index, video);
                syncWatchProgress(episode, video, { force: true });
              }}
            >
              <div className="relative h-[3px] w-full overflow-visible rounded-full bg-white/30">
                {seekPreview?.index === index && (
                  <span
                    className="pointer-events-none absolute bottom-[11px] z-10 whitespace-nowrap rounded-md bg-neutral-900/80 px-2 py-1 text-[11px] leading-none text-white"
                    style={{
                      left: `clamp(48px, ${seekPreview.ratio * 100}%, calc(100% - 48px))`,
                      transform: 'translateX(-50%)',
                    }}
                  >
                    {formatTime(seekPreview.time)} / {formatTime(videoRefs.current[index]?.duration ?? 0)}
                  </span>
                )}
                <div className="h-full rounded-full bg-white" style={{ width: `${(progress[index] || 0) * 100}%` }} />
                <span
                  className={`absolute top-1/2 block -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow-sm transition-[width,height] ${
                    draggingIndex === index ? 'h-3 w-3' : 'h-2 w-2'
                  }`}
                  style={{ left: `${(progress[index] || 0) * 100}%` }}
                />
              </div>
            </div>
          </article>
        ))}
      </section>

      {commentEpisode ? (
        <section
          data-video-control
          className="absolute inset-x-0 bottom-[70px] z-[100] rounded-t-2xl border-t border-white/10 bg-background/95 px-margin-page pb-4 pt-3 text-on-surface shadow-2xl backdrop-blur-2xl"
          onClick={(event) => event.stopPropagation()}
          onPointerDown={(event) => event.stopPropagation()}
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="min-w-0">
              <h2 className="text-headline-md font-semibold">评论</h2>
              <p className="truncate text-label-md text-on-surface-variant">{commentEpisode.title}</p>
            </div>
            <button className="rounded-xl bg-white/8 px-3 py-2 text-label-md" type="button" onClick={() => setCommentEpisode(null)}>
              关闭
            </button>
          </div>
          <div className="mb-3 max-h-48 space-y-2 overflow-y-auto">
            {comments.length ? comments.map((item) => (
              <article key={item.id} className="rounded-xl bg-white/6 px-3 py-2">
                <p className="mb-1 text-label-md text-primary">{item.displayName}</p>
                <p className="text-body-sm text-on-surface">{item.content}</p>
              </article>
            )) : (
              <p className="rounded-xl bg-white/6 px-3 py-4 text-center text-body-sm text-on-surface-variant">
                {commentError || '暂无评论'}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <input
              className="h-11 min-w-0 flex-1 rounded-xl border-white/10 bg-white/8 px-3 text-body-sm text-on-surface placeholder:text-on-surface-variant"
              value={commentInput}
              onChange={(event) => setCommentInput(event.target.value)}
              placeholder="写下你的评论"
              onKeyDown={(event) => {
                if (event.key === 'Enter') void submitComment();
              }}
            />
            <button className="primary-gradient h-11 rounded-xl px-4 text-body-sm font-semibold text-white" type="button" onClick={() => void submitComment()}>
              发送
            </button>
          </div>
          {commentError && comments.length ? <p className="mt-2 text-label-md text-error">{commentError}</p> : null}
        </section>
      ) : null}

      <BottomNav />
    </main>
  );
}
