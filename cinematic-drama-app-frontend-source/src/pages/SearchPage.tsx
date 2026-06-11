import { Bot, Search, Sparkles } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { EmptyState, ErrorState, LoadingState } from '../components/PageState';
import { loadDramas } from '../data/catalog';
import type { DramaItem } from '../data/catalog';

function isVideoUrl(value: string) {
  return value.includes('/api/videos/') || /\.(mp4|webm|mov|m4v)(\?|$)/i.test(value);
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [dramas, setDramas] = useState<DramaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDramas(await loadDramas());
    } catch (err) {
      setError(err instanceof Error ? err.message : '搜索数据加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const results = useMemo(() => {
    const keyword = query.trim();
    if (!keyword) return dramas;
    return dramas.filter((drama) => `${drama.title}${drama.subtitle}${drama.description}${drama.genre.join('')}`.includes(keyword));
  }, [dramas, query]);

  if (loading) return <LoadingState title="正在加载搜索数据" />;
  if (error) return <ErrorState title="搜索不可用" message={error} onAction={reload} />;

  return (
    <main className="phone-safe min-h-dvh pb-24 pt-5">
      <header className="px-margin-page pb-4">
        <h1 className="text-display-lg font-bold">搜索</h1>
      </header>

      <section className="px-margin-page">
        <label className="glass-panel flex h-12 items-center gap-2 rounded-2xl px-3">
          <Search size={18} className="text-on-surface-variant" />
          <input
            className="min-w-0 flex-1 border-0 bg-transparent p-0 text-body-sm text-on-surface placeholder:text-on-surface-variant focus:ring-0"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜剧名、题材、情绪点"
          />
        </label>

        <Link className="primary-gradient mt-3 flex h-12 items-center justify-center gap-2 rounded-2xl font-bold text-white" to="/ai">
          <Bot size={18} />
          进入 AI 沉浸式搜索
        </Link>
      </section>

      <section className="px-margin-page py-stack-lg">
        <h2 className="mb-stack-sm text-headline-md font-semibold">综合结果</h2>
        {results.length ? (
          <div className="space-y-3">
            {results.map((drama) => (
              <Link key={drama.id} className="glass-panel flex gap-3 rounded-2xl p-3" to={`/detail?drama=${drama.id}`}>
                {isVideoUrl(drama.poster) ? (
                  <video className="h-28 w-20 rounded-xl object-cover" src={drama.poster} muted playsInline preload="metadata" />
                ) : (
                  <img className="h-28 w-20 rounded-xl object-cover" src={drama.poster} alt={drama.title} />
                )}
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <h3 className="truncate text-body-lg font-bold">{drama.title}</h3>
                    <span className="rounded-full bg-primary/15 px-2 py-0.5 text-label-sm text-primary">{drama.score}</span>
                  </div>
                  <p className="text-label-md text-on-surface-variant">{drama.subtitle}</p>
                  <p className="line-clamp-2 text-body-sm text-on-surface-variant">{drama.description}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {drama.genre.map((tag) => (
                      <span key={tag} className="rounded bg-white/8 px-2 py-0.5 text-label-sm text-on-surface-variant">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState title="没有匹配结果" message="换一个剧名、题材或情绪点再试。" />
        )}
      </section>

      <section className="px-margin-page">
        <h2 className="mb-stack-sm text-headline-md font-semibold">热搜情绪</h2>
        <div className="flex flex-wrap gap-2">
          {['打脸爽点', '扮猪吃虎', '高燃反转', '长按守护', 'AI 预测下一集'].map((item) => (
            <button key={item} className="glass-panel flex items-center gap-1 rounded-full px-3 py-2 text-label-md" type="button" onClick={() => setQuery(item)}>
              <Sparkles size={14} className="text-primary" />
              {item}
            </button>
          ))}
        </div>
      </section>

      <BottomNav />
    </main>
  );
}
