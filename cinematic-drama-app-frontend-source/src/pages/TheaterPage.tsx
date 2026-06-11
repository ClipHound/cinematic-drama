import { ChevronRight, Play, Star } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { EmptyState, ErrorState, LoadingState } from '../components/PageState';
import SectionTitle from '../components/SectionTitle';
import { loadDramas } from '../data/catalog';
import type { DramaItem } from '../data/catalog';

function isVideoUrl(value: string) {
  return value.includes('/api/videos/') || /\.(mp4|webm|mov|m4v)(\?|$)/i.test(value);
}

export default function TheaterPage() {
  const [dramas, setDramas] = useState<DramaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDramas(await loadDramas());
    } catch (err) {
      setError(err instanceof Error ? err.message : '剧场数据加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (loading) return <LoadingState title="正在加载剧场" />;
  if (error) return <ErrorState title="剧场不可用" message={error} onAction={reload} />;

  const featuredDrama = dramas.find((item) => item.episodes.length > 0) || dramas[0] || null;
  const featuredEpisode = featuredDrama?.episodes[1] ?? featuredDrama?.episodes[0];

  return (
    <main className="phone-safe min-h-dvh pb-24 pt-5">
      <header className="px-margin-page pb-4">
        <p className="text-label-md text-primary">发现与选集</p>
        <h1 className="text-display-lg font-bold text-on-surface">剧场</h1>
      </header>

      {featuredDrama ? (
        <section className="px-margin-page pb-stack-lg">
          <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-surface-container">
            {featuredEpisode ? (
              <video className="h-56 w-full object-cover opacity-80" src={featuredEpisode.videoUrl} muted loop playsInline autoPlay />
            ) : isVideoUrl(featuredDrama.cover) ? (
              <video className="h-56 w-full object-cover opacity-80" src={featuredDrama.cover} muted loop playsInline autoPlay />
            ) : (
              <img className="h-56 w-full object-cover opacity-80" src={featuredDrama.cover} alt={featuredDrama.title} />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black via-black/25 to-transparent" />
            <div className="absolute bottom-0 left-0 right-0 p-4">
              <span className="mb-2 inline-flex items-center gap-1 rounded-full bg-primary/20 px-2 py-1 text-label-sm text-primary">
                <Star size={13} fill="currentColor" />
                本周主推
              </span>
              <h2 className="text-display-lg-mobile font-bold">{featuredDrama.title}</h2>
              <p className="line-clamp-2 text-body-sm text-white/70">{featuredDrama.description}</p>
            </div>
          </div>
        </section>
      ) : (
        <section className="px-margin-page pb-stack-lg">
          <EmptyState title="暂无剧目" message="后端还没有返回可展示的剧目。" />
        </section>
      )}

      {featuredDrama ? (
        <section className="pb-stack-lg">
          <SectionTitle action={<Link className="flex items-center text-label-md text-on-surface-variant" to={`/detail?drama=${featuredDrama.id}`}>作品详情 <ChevronRight size={16} /></Link>}>
            全部剧集
          </SectionTitle>
          {featuredDrama.episodes.length ? (
            <div className="grid grid-cols-4 gap-2 px-margin-page">
              {featuredDrama.episodes.map((episode) => (
                <Link
                  key={episode.id}
                  className="glass-panel flex h-16 flex-col items-center justify-center rounded-xl text-center"
                  to={`/player?drama=${featuredDrama.id}&episode=${episode.episodeNumber}`}
                >
                  <span className="text-body-lg font-bold">{episode.episodeNumber}</span>
                  <span className="text-[10px] text-on-surface-variant">{episode.durationLabel}</span>
                </Link>
              ))}
            </div>
          ) : (
            <div className="px-margin-page">
              <EmptyState title="暂无可播放剧集" message="该作品还没有完成视频入库。" />
            </div>
          )}
        </section>
      ) : null}

      <section>
        <SectionTitle>猜你喜欢</SectionTitle>
        {dramas.length ? (
          <div className="space-y-3 px-margin-page">
            {dramas.map((drama) => (
              <Link key={drama.id} className="glass-panel flex gap-3 rounded-2xl p-3" to={`/detail?drama=${drama.id}`}>
                {isVideoUrl(drama.poster) ? (
                  <video className="h-24 w-16 rounded-xl object-cover" src={drama.poster} muted playsInline preload="metadata" />
                ) : (
                  <img className="h-24 w-16 rounded-xl object-cover" src={drama.poster} alt={drama.title} />
                )}
                <div className="min-w-0 flex-1">
                  <h3 className="text-body-lg font-bold">{drama.title}</h3>
                  <p className="text-label-md text-primary">{drama.subtitle}</p>
                  <p className="line-clamp-2 text-body-sm text-on-surface-variant">{drama.description}</p>
                  <span className="mt-2 inline-flex items-center gap-1 text-label-md text-on-surface-variant">
                    <Play size={13} /> {drama.episodes.length} 集
                  </span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="px-margin-page">
            <EmptyState title="暂无推荐" message="剧目入库后会出现在这里。" />
          </div>
        )}
      </section>

      <BottomNav />
    </main>
  );
}
