import { Bot, ChevronRight, Play, Search, Sparkles, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { EmptyState, ErrorState, LoadingState } from '../components/PageState';
import { loadDramas, requestSearch } from '../data/catalog';
import type { AiSearchResult, DramaItem } from '../data/catalog';

const hotKeywords = ['天下第一纨绔', '古装', '权谋', '爽剧', '互动', '比武招亲'];

function isVideoUrl(value: string) {
  return value.includes('/api/videos/') || /\.(mp4|webm|mov|m4v)(\?|$)/i.test(value);
}

function resultHref(result: AiSearchResult) {
  if (result.type === 'episode' && result.episodeNumber) {
    return `/player?drama=${result.dramaId}&episode=${result.episodeNumber}`;
  }
  return `/detail?drama=${result.dramaId}`;
}

function DramaCard({ drama }: { drama: DramaItem }) {
  const firstEpisode = drama.episodes[0];
  return (
    <Link className="flex gap-3 rounded-2xl border border-white/8 bg-white/[0.04] p-3" to={`/detail?drama=${drama.id}`}>
      {isVideoUrl(drama.poster) ? (
        <video className="h-28 w-20 shrink-0 rounded-xl object-cover" src={drama.poster} muted playsInline preload="metadata" />
      ) : (
        <img className="h-28 w-20 shrink-0 rounded-xl object-cover" src={drama.poster} alt={drama.title} />
      )}
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <h3 className="truncate text-body-lg font-bold">{drama.title}</h3>
          <span className="shrink-0 rounded-full bg-primary/15 px-2 py-0.5 text-label-sm text-primary">{drama.score}</span>
        </div>
        <p className="line-clamp-1 text-label-md text-primary">{drama.subtitle}</p>
        <p className="line-clamp-2 text-body-sm text-on-surface-variant">{drama.description}</p>
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="line-clamp-1 text-label-md text-on-surface-variant">{drama.genre.join(' · ')}</span>
          {firstEpisode ? (
            <span className="inline-flex shrink-0 items-center gap-1 text-label-md text-on-surface-variant">
              <Play size={13} />
              {drama.episodes.length} 集
            </span>
          ) : null}
        </div>
      </div>
    </Link>
  );
}

function SearchResultCard({ result }: { result: AiSearchResult }) {
  const isEpisode = result.type === 'episode' && result.episodeNumber;
  const [imageFailed, setImageFailed] = useState(false);
  return (
    <Link className="flex gap-3 rounded-2xl border border-white/8 bg-white/[0.04] p-3" to={resultHref(result)}>
      {result.poster && !imageFailed ? (
        <img className="h-24 w-16 shrink-0 rounded-xl object-cover" src={result.poster} alt={result.title} onError={() => setImageFailed(true)} />
      ) : (
        <span className="grid h-24 w-16 shrink-0 place-items-center rounded-xl bg-white/8 text-primary">
          {isEpisode ? <Play size={20} fill="currentColor" /> : <Search size={20} />}
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="mb-1 inline-flex rounded-full bg-primary/15 px-2 py-0.5 text-label-sm text-primary">
          {isEpisode ? `第 ${result.episodeNumber} 集` : '剧目'}
        </span>
        <strong className="line-clamp-1 text-body-lg text-on-surface">{result.title}</strong>
        {result.snippet || result.subtitle ? (
          <span className="line-clamp-2 text-body-sm text-on-surface-variant">{result.snippet || result.subtitle}</span>
        ) : null}
      </span>
      <ChevronRight size={18} className="mt-9 shrink-0 text-on-surface-variant" />
    </Link>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [results, setResults] = useState<AiSearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [pending, setPending] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
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

  const recommendations = useMemo(() => dramas.slice(0, 8), [dramas]);

  const submitSearch = async (text = query) => {
    const value = text.trim();
    if (!value) {
      setSearchError('请输入搜索关键词');
      setSearched(false);
      setSubmittedQuery('');
      setResults([]);
      return;
    }

    setQuery(value);
    setSubmittedQuery(value);
    setSearched(true);
    setPending(true);
    setSearchError(null);
    try {
      const payload = await requestSearch(value);
      setResults(payload.results);
    } catch (err) {
      setResults([]);
      setSearchError(err instanceof Error ? err.message : '搜索失败');
    } finally {
      setPending(false);
    }
  };

  const clearSearch = () => {
    setQuery('');
    setSubmittedQuery('');
    setResults([]);
    setSearched(false);
    setSearchError(null);
  };

  if (loading) return <LoadingState title="正在加载搜索数据" />;
  if (error) return <ErrorState title="搜索不可用" message={error} onAction={reload} />;

  return (
    <main className="phone-safe min-h-dvh pb-24 pt-5">
      <header className="px-margin-page pb-4">
        <p className="text-label-md text-primary">剧目与剧集</p>
        <h1 className="text-display-lg font-bold">搜索</h1>
      </header>

      <section className="px-margin-page">
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void submitSearch();
          }}
        >
          <label className="glass-panel flex h-12 min-w-0 flex-1 items-center gap-2 rounded-2xl px-3">
            <Search size={18} className="shrink-0 text-on-surface-variant" />
            <input
              className="min-w-0 flex-1 border-0 bg-transparent p-0 text-body-sm text-on-surface placeholder:text-on-surface-variant focus:ring-0"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                if (searchError) setSearchError(null);
              }}
              placeholder="搜剧名、题材、互动点"
            />
            {query ? (
              <button className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white/8 text-on-surface-variant" type="button" aria-label="清空搜索" onClick={clearSearch}>
                <X size={14} />
              </button>
            ) : null}
          </label>
          <button className="primary-gradient flex h-12 shrink-0 items-center justify-center gap-1 rounded-2xl px-4 text-body-sm font-bold text-white disabled:opacity-60" type="submit" disabled={pending}>
            <Search size={16} />
            搜索
          </button>
        </form>

        {searchError ? <p className="mt-2 rounded-xl bg-error/10 px-3 py-2 text-label-md text-error">{searchError}</p> : null}

        <div className="mt-3 flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.04] px-3 py-2">
          <span className="flex min-w-0 items-center gap-2 text-label-md text-on-surface-variant">
            <Bot size={15} className="shrink-0 text-primary" />
            想用自然语言描述剧情？
          </span>
          <Link className="shrink-0 rounded-full bg-white/8 px-3 py-1.5 text-label-md text-primary" to="/ai">
            AI 搜索
          </Link>
        </div>
      </section>

      <section className="px-margin-page py-stack-md">
        <h2 className="mb-stack-sm text-headline-md font-semibold">热搜关键词</h2>
        <div className="flex flex-wrap gap-2">
          {hotKeywords.map((item) => (
            <button key={item} className="glass-panel flex items-center gap-1 rounded-full px-3 py-2 text-label-md" type="button" onClick={() => void submitSearch(item)}>
              <Sparkles size={14} className="text-primary" />
              {item}
            </button>
          ))}
        </div>
      </section>

      <section className="px-margin-page pb-stack-lg">
        <div className="mb-stack-sm flex items-center justify-between">
          <h2 className="text-headline-md font-semibold">{searched ? '搜索结果' : '推荐内容'}</h2>
          {searched ? <span className="text-label-md text-on-surface-variant">{pending ? '搜索中' : submittedQuery}</span> : null}
        </div>

        {pending ? (
          <div className="glass-panel rounded-2xl p-5 text-center text-body-sm text-on-surface-variant">正在搜索...</div>
        ) : searched ? (
          results.length ? (
            <div className="space-y-3">
              {results.map((result) => (
                <SearchResultCard key={`${result.type}-${result.dramaId}-${result.episodeNumber || 'detail'}`} result={result} />
              ))}
            </div>
          ) : (
            <EmptyState title="没有匹配结果" message="换一个剧名、题材或互动点再试。" />
          )
        ) : recommendations.length ? (
          <div className="space-y-3">
            {recommendations.map((drama) => (
              <DramaCard key={drama.id} drama={drama} />
            ))}
          </div>
        ) : (
          <EmptyState title="暂无推荐" message="剧目入库后会出现在这里。" />
        )}
      </section>

      <BottomNav />
    </main>
  );
}
