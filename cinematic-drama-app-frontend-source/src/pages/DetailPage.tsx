import { Play, Star } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { EmptyState, ErrorState, LoadingState } from '../components/PageState';
import SectionTitle from '../components/SectionTitle';
import TopBar from '../components/TopBar';
import { loadDrama } from '../data/catalog';
import type { DramaItem } from '../data/catalog';

function isVideoUrl(value: string) {
  return value.includes('/api/videos/') || /\.(mp4|webm|mov|m4v)(\?|$)/i.test(value);
}

export default function DetailPage() {
  const [searchParams] = useSearchParams();
  const dramaId = searchParams.get('drama') || '';
  const [drama, setDrama] = useState<DramaItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDrama(await loadDrama(dramaId));
    } catch (err) {
      setError(err instanceof Error ? err.message : '作品详情加载失败');
    } finally {
      setLoading(false);
    }
  }, [dramaId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (loading) return <LoadingState title="正在加载作品详情" />;
  if (error) return <ErrorState title="作品详情不可用" message={error} onAction={reload} />;
  if (!drama) return <ErrorState title="作品不存在" message="后端没有返回该作品。" onAction={reload} />;

  const firstEpisode = drama.episodes[0];
  const posterIsVideo = isVideoUrl(drama.poster);

  return (
    <main className="phone-safe relative pb-28 pt-14">
      <TopBar title={drama.title} />

      <section className="flex gap-margin-page px-margin-page py-stack-md">
        <div className="w-1/3 shrink-0">
          <div className="aspect-poster relative overflow-hidden rounded-xl border border-white/10 bg-surface-container shadow-2xl">
            {posterIsVideo ? (
              <video className="h-full w-full object-cover" src={drama.poster} muted playsInline preload="metadata" />
            ) : (
              <img className="h-full w-full object-cover" src={drama.poster} alt={drama.title} />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
          </div>
        </div>

        <div className="min-w-0 flex-1 pt-2">
          <h1 className="mb-2 text-display-lg-mobile font-bold text-on-surface">{drama.title}</h1>
          <p className="mb-3 text-label-md text-primary">{drama.subtitle}</p>
          <div className="flex flex-wrap gap-2">
            <span className="glass-panel rounded-full px-3 py-1 text-label-sm text-primary">{drama.score}</span>
            <span className="glass-panel rounded-full px-3 py-1 text-label-sm text-on-surface-variant">{drama.heat}</span>
            {drama.genre.map((genre) => (
              <span key={genre} className="glass-panel rounded-full px-3 py-1 text-label-sm text-on-surface-variant">
                {genre}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="px-margin-page py-stack-md">
        <h2 className="mb-stack-sm text-headline-md font-semibold">作品介绍</h2>
        <p className="text-body-sm leading-relaxed text-on-surface-variant">{drama.description}</p>
      </section>

      <section className="py-stack-md">
        <SectionTitle>选集</SectionTitle>
        {drama.episodes.length > 0 ? (
          <div className="grid grid-cols-4 gap-2 px-margin-page">
            {drama.episodes.map((episode) => (
              <Link
                key={episode.id}
                className="glass-panel flex h-16 flex-col items-center justify-center rounded-xl"
                to={`/player?drama=${drama.id}&episode=${episode.episodeNumber}`}
              >
                <strong className="text-body-lg">{episode.episodeNumber}</strong>
                <span className="text-label-sm text-on-surface-variant">{episode.durationLabel}</span>
              </Link>
            ))}
          </div>
        ) : (
          <div className="px-margin-page">
            <EmptyState title="暂无可播放剧集" message="该作品还没有完成视频入库或互动配置生成。" />
          </div>
        )}
      </section>

      {firstEpisode ? (
        <footer className="fixed bottom-[70px] left-1/2 z-40 w-full max-w-[430px] -translate-x-1/2 bg-background/80 px-margin-page pb-4 pt-3 backdrop-blur-2xl">
          <Link
            className="primary-gradient flex h-14 items-center justify-center gap-2 rounded-2xl font-bold text-white"
            to={`/player?drama=${drama.id}&episode=${firstEpisode.episodeNumber}`}
          >
            <Play size={20} fill="currentColor" />
            立即观看
          </Link>
        </footer>
      ) : (
        <footer className="fixed bottom-[70px] left-1/2 z-40 flex w-full max-w-[430px] -translate-x-1/2 items-center justify-center gap-2 bg-background/80 px-margin-page pb-4 pt-3 text-on-surface-variant backdrop-blur-2xl">
          <Star size={18} />
          敬请期待
        </footer>
      )}

      <BottomNav />
    </main>
  );
}
