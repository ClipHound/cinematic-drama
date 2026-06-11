import {
  Bell,
  BookmarkCheck,
  ChevronRight,
  Heart,
  Play,
  RefreshCw,
  Settings,
  Star,
  Trash2,
  UserRound,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { EmptyState, ErrorState, LoadingState } from '../components/PageState';
import {
  loadFavoriteDramas,
  loadHistory,
  loadProfile,
  type FavoriteDramaItem,
  type InteractionRecordItem,
  type UserHistory,
  type UserProfile,
  type WatchProgressItem,
} from '../data/profile';
import { setFavorite } from '../data/social';

type ProfileView = 'overview' | 'favorites' | 'history' | 'interactions';

const viewTitles: Record<ProfileView, string> = {
  overview: '我的',
  favorites: '我的收藏',
  history: '观看历史',
  interactions: '互动记录',
};

const eventTypeText: Record<string, string> = {
  like: '喜欢',
  comment_open: '打开评论',
  celebrate_click: '互动点击',
  team_choose: '阵营选择',
  prediction_submit: '预测提交',
  clue_judge: '线索判断',
  interaction: '互动',
};

function normalizeView(value: string | null): ProfileView {
  if (value === 'favorites' || value === 'history' || value === 'interactions') return value;
  return 'overview';
}

function formatTime(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return '00:00';
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return [hours, minutes, seconds].map((part) => String(part).padStart(2, '0')).join(':');
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function formatDate(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function progressPercent(item: WatchProgressItem) {
  if (!item.durationMs) return 0;
  return Math.max(0, Math.min(100, Math.round((item.progressMs / item.durationMs) * 100)));
}

function ProfileHeader({
  profile,
  title,
  activeView,
  onViewChange,
  onNotice,
  onRefresh,
}: {
  profile: UserProfile;
  title: string;
  activeView: ProfileView;
  onViewChange: (view: ProfileView) => void;
  onNotice: (text: string) => void;
  onRefresh: () => void;
}) {
  const stats = [
    { label: '已看', value: profile.stats.watchedEpisodes, view: 'history' as ProfileView },
    { label: '互动', value: profile.stats.interactions, view: 'interactions' as ProfileView },
    { label: '收藏', value: profile.stats.favorites, view: 'favorites' as ProfileView },
  ];

  return (
    <>
      <header className="flex items-center justify-between px-margin-page pb-4">
        <div>
          <p className="text-label-md text-primary">个人中心</p>
          <h1 className="text-display-lg font-bold">{title}</h1>
        </div>
        <div className="flex gap-2">
          <button className="icon-button glass-panel" type="button" aria-label="刷新" onClick={onRefresh}>
            <RefreshCw size={18} />
          </button>
          <button className="icon-button glass-panel" type="button" aria-label="通知" onClick={() => onNotice('暂无新通知')}>
            <Bell size={19} />
          </button>
          <button className="icon-button glass-panel" type="button" aria-label="设置" onClick={() => onNotice('设置功能待后续开放')}>
            <Settings size={19} />
          </button>
        </div>
      </header>

      <section className="px-margin-page">
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-surface-container">
          <div className="relative p-4">
            <div className="absolute inset-x-0 top-0 h-20 bg-gradient-to-r from-primary-container/35 via-secondary-container/20 to-tertiary-container/20" />
            <div className="relative flex items-center gap-3">
              <div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-primary-container text-xl font-bold text-white shadow-lg">
                {profile.avatarText}
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-headline-md font-bold">{profile.displayName}</h2>
                <p className="line-clamp-2 text-body-sm text-on-surface-variant">{profile.bio}</p>
              </div>
              <UserRound size={20} className="shrink-0 text-primary" />
            </div>

            <div className="relative mt-4 grid grid-cols-3 rounded-2xl bg-black/18 p-1">
              {stats.map((item) => (
                <button
                  key={item.label}
                  className={`rounded-xl px-2 py-2 text-center transition ${activeView === item.view ? 'bg-white/10' : ''}`}
                  type="button"
                  onClick={() => onViewChange(item.view)}
                >
                  <strong className="block text-body-lg">{item.value}</strong>
                  <span className="text-label-md text-on-surface-variant">{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function OverviewPanel({ profile, notice }: { profile: UserProfile; notice: string | null }) {
  const continueWatching = profile.continueWatching;
  const menuItems = [
    { label: '我的收藏', sub: `${profile.stats.favorites} 部短剧`, Icon: Heart, href: '/profile?view=favorites' },
    { label: '观看历史', sub: `${profile.stats.watchedEpisodes} 集进度`, Icon: BookmarkCheck, href: '/profile?view=history' },
    { label: '互动记录', sub: `${profile.stats.interactions} 次互动`, Icon: Star, href: '/profile?view=interactions' },
  ];

  return (
    <>
      <section className="px-margin-page pt-4">
        {continueWatching ? (
          <Link
            className="primary-gradient flex items-center gap-3 rounded-2xl p-4 text-white shadow-xl"
            to={`/player?drama=${continueWatching.dramaId}&episode=${continueWatching.episodeNumber}`}
          >
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white/18">
              <Play size={19} fill="currentColor" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-label-md text-white/75">继续观看</span>
              <strong className="line-clamp-1 text-body-lg">{continueWatching.title}</strong>
            </span>
            <ChevronRight size={19} className="shrink-0" />
          </Link>
        ) : (
          <Link className="glass-panel flex items-center gap-3 rounded-2xl p-4" to="/home">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white/8 text-primary">
              <Play size={19} fill="currentColor" />
            </span>
            <span className="min-w-0 flex-1">
              <strong className="block text-body-lg">开始观看</strong>
              <span className="text-label-md text-on-surface-variant">暂无观看记录，去首页看看</span>
            </span>
            <ChevronRight size={19} className="shrink-0 text-on-surface-variant" />
          </Link>
        )}
        {notice ? <p className="mt-3 rounded-xl bg-white/6 px-3 py-2 text-label-md text-on-surface-variant">{notice}</p> : null}
      </section>

      <section className="space-y-2 px-margin-page py-stack-md">
        {menuItems.map(({ label, sub, Icon, href }) => (
          <Link key={label} className="flex items-center gap-3 rounded-2xl bg-white/[0.04] px-4 py-3" to={href}>
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/8 text-primary">
              <Icon size={19} />
            </span>
            <span className="min-w-0 flex-1">
              <strong className="block text-body-lg">{label}</strong>
              <span className="line-clamp-1 text-label-md text-on-surface-variant">{sub}</span>
            </span>
            <ChevronRight size={18} className="shrink-0 text-on-surface-variant" />
          </Link>
        ))}
      </section>
    </>
  );
}

function FavoriteList({
  items,
  onRemove,
}: {
  items: FavoriteDramaItem[];
  onRemove: (dramaId: string) => void;
}) {
  if (!items.length) {
    return (
      <section className="px-margin-page py-stack-lg">
        <EmptyState title="还没有收藏" message="在首页点喜欢后，这里会同步出现对应短剧。" />
      </section>
    );
  }

  return (
    <section className="space-y-3 px-margin-page py-stack-md">
      {items.map((item) => (
        <article key={item.id} className="flex gap-3 rounded-2xl border border-white/8 bg-white/[0.04] p-3">
          <Link className="h-28 w-20 shrink-0 overflow-hidden rounded-xl bg-white/6" to={`/detail?drama=${item.id}`}>
            <img className="h-full w-full object-cover" src={item.poster || item.cover} alt={item.title} />
          </Link>
          <div className="min-w-0 flex-1">
            <Link className="block" to={`/detail?drama=${item.id}`}>
              <h2 className="line-clamp-1 text-body-lg font-semibold text-on-surface">{item.title}</h2>
              <p className="line-clamp-2 pt-1 text-body-sm text-on-surface-variant">{item.description || item.subtitle}</p>
            </Link>
            <p className="pt-2 text-label-md text-on-surface-variant">
              {item.favoriteAt ? `收藏于 ${formatDate(item.favoriteAt)}` : item.heat}
            </p>
            <div className="mt-3 flex gap-2">
              <Link
                className="primary-gradient flex h-9 flex-1 items-center justify-center gap-1 rounded-xl text-label-md font-semibold text-white"
                to={`/player?drama=${item.id}&episode=${item.firstEpisodeNumber || 1}`}
              >
                <Play size={15} fill="currentColor" />
                播放
              </Link>
              <button
                className="grid h-9 w-10 place-items-center rounded-xl bg-white/8 text-on-surface-variant"
                type="button"
                aria-label={`取消收藏 ${item.title}`}
                onClick={() => onRemove(item.id)}
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}

function HistoryList({ items }: { items: WatchProgressItem[] }) {
  if (!items.length) {
    return (
      <section className="px-margin-page py-stack-lg">
        <EmptyState title="还没有观看历史" message="播放或拖动视频进度后，这里会显示最近观看进度。" />
      </section>
    );
  }

  return (
    <section className="space-y-3 px-margin-page py-stack-md">
      {items.map((item) => {
        const percent = progressPercent(item);
        return (
          <Link
            key={item.episodeId}
            className="block rounded-2xl border border-white/8 bg-white/[0.04] p-4"
            to={`/player?drama=${item.dramaId}&episode=${item.episodeNumber}`}
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="line-clamp-1 text-body-lg font-semibold text-on-surface">{item.title}</h2>
                <p className="pt-1 text-label-md text-on-surface-variant">最近观看 {formatDate(item.updatedAt)}</p>
              </div>
              <span className="shrink-0 rounded-full bg-white/8 px-2 py-1 text-label-sm text-primary">{percent}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
            </div>
            <div className="mt-2 flex items-center justify-between text-label-md text-on-surface-variant">
              <span>{formatTime(item.progressMs)}</span>
              <span>{formatTime(item.durationMs)}</span>
            </div>
          </Link>
        );
      })}
    </section>
  );
}

function InteractionList({ items }: { items: InteractionRecordItem[] }) {
  if (!items.length) {
    return (
      <section className="px-margin-page py-stack-lg">
        <EmptyState title="还没有互动记录" message="点击剧情互动、喜欢或评论入口后，这里会记录行为。" />
      </section>
    );
  }

  return (
    <section className="space-y-3 px-margin-page py-stack-md">
      {items.map((item) => (
        <Link
          key={item.eventId}
          className="flex items-center gap-3 rounded-2xl border border-white/8 bg-white/[0.04] p-4"
          to={`/player?drama=${item.dramaId}&episode=${item.episodeNumber}`}
        >
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/8 text-primary">
            <Star size={18} />
          </span>
          <span className="min-w-0 flex-1">
            <strong className="line-clamp-1 text-body-lg">
              {eventTypeText[item.eventType] || item.eventType}
              {item.pointTitle ? ` · ${item.pointTitle}` : ''}
            </strong>
            <span className="line-clamp-1 text-label-md text-on-surface-variant">
              {item.dramaTitle} · 第 {item.episodeNumber} 集 · {formatTime(item.atMs)}
            </span>
            <span className="block text-label-md text-on-surface-variant">{formatDate(item.receivedAt)}</span>
          </span>
          <ChevronRight size={18} className="shrink-0 text-on-surface-variant" />
        </Link>
      ))}
    </section>
  );
}

export default function ProfilePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const view = normalizeView(searchParams.get('view'));
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [favorites, setFavorites] = useState<FavoriteDramaItem[]>([]);
  const [history, setHistory] = useState<UserHistory>({ watchProgress: [], interactions: [] });
  const [loading, setLoading] = useState(true);
  const [sectionLoading, setSectionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sectionError, setSectionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const setView = (nextView: ProfileView) => {
    if (nextView === 'overview') setSearchParams({});
    else setSearchParams({ view: nextView });
  };

  const reloadProfile = useCallback(async () => {
    setError(null);
    setProfile(await loadProfile());
  }, []);

  const reloadSection = useCallback(async (nextView: ProfileView) => {
    if (nextView === 'overview') {
      setSectionLoading(false);
      setSectionError(null);
      return;
    }
    setSectionLoading(true);
    setSectionError(null);
    try {
      if (nextView === 'favorites') {
        setFavorites(await loadFavoriteDramas());
      } else {
        setHistory(await loadHistory());
      }
    } catch (err) {
      setSectionError(err instanceof Error ? err.message : '数据加载失败');
    } finally {
      setSectionLoading(false);
    }
  }, []);

  const reloadAll = useCallback(async () => {
    setLoading(true);
    try {
      await reloadProfile();
      await reloadSection(view);
    } catch (err) {
      setError(err instanceof Error ? err.message : '用户资料加载失败');
    } finally {
      setLoading(false);
    }
  }, [reloadProfile, reloadSection, view]);

  useEffect(() => {
    void reloadAll();
  }, [reloadAll]);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const activeItems = useMemo(() => {
    if (view === 'history') return history.watchProgress;
    if (view === 'interactions') return history.interactions;
    return [];
  }, [history, view]);

  const removeFavorite = async (dramaId: string) => {
    const current = favorites;
    setFavorites((items) => items.filter((item) => item.id !== dramaId));
    try {
      await setFavorite(dramaId, false);
      setProfile(await loadProfile());
      setNotice('已取消收藏');
    } catch (err) {
      setFavorites(current);
      setNotice(err instanceof Error ? err.message : '取消收藏失败');
    }
  };

  if (loading) return <LoadingState title="正在加载我的资料" />;
  if (error || !profile) return <ErrorState title="我的页面不可用" message={error || '用户资料为空'} onAction={reloadAll} />;

  return (
    <main className="phone-safe min-h-dvh pb-24 pt-5">
      <ProfileHeader
        profile={profile}
        title={viewTitles[view]}
        activeView={view}
        onViewChange={setView}
        onNotice={setNotice}
        onRefresh={() => void reloadAll()}
      />

      <section className="sticky top-0 z-30 bg-background/88 px-margin-page pt-4 backdrop-blur-xl">
        <div className="hide-scrollbar flex gap-2 overflow-x-auto pb-3">
          {(['overview', 'favorites', 'history', 'interactions'] as ProfileView[]).map((item) => (
            <button
              key={item}
              className={`h-9 shrink-0 rounded-full px-4 text-label-md transition ${
                view === item ? 'bg-primary-container text-white shadow-lg' : 'bg-white/8 text-on-surface-variant'
              }`}
              type="button"
              onClick={() => setView(item)}
            >
              {viewTitles[item]}
            </button>
          ))}
        </div>
      </section>

      {notice ? <p className="mx-margin-page mt-3 rounded-xl bg-white/6 px-3 py-2 text-label-md text-on-surface-variant">{notice}</p> : null}

      {view === 'overview' ? <OverviewPanel profile={profile} notice={null} /> : null}

      {sectionError && view !== 'overview' ? (
        <section className="px-margin-page py-stack-md">
          <div className="rounded-2xl border border-error/30 bg-error/10 p-4 text-center">
            <h2 className="text-body-lg font-semibold text-on-surface">{viewTitles[view]}不可用</h2>
            <p className="mt-1 text-body-sm text-on-surface-variant">{sectionError}</p>
            <button className="mt-3 rounded-xl bg-white/10 px-4 py-2 text-label-md" type="button" onClick={() => void reloadSection(view)}>
              重新加载
            </button>
          </div>
        </section>
      ) : null}

      {sectionLoading && view !== 'overview' ? (
        <section className="px-margin-page py-stack-lg">
          <div className="glass-panel rounded-2xl p-5 text-center text-body-sm text-on-surface-variant">正在加载{viewTitles[view]}</div>
        </section>
      ) : null}

      {!sectionLoading && !sectionError && view === 'favorites' ? <FavoriteList items={favorites} onRemove={(id) => void removeFavorite(id)} /> : null}
      {!sectionLoading && !sectionError && view === 'history' ? <HistoryList items={activeItems as WatchProgressItem[]} /> : null}
      {!sectionLoading && !sectionError && view === 'interactions' ? <InteractionList items={activeItems as InteractionRecordItem[]} /> : null}

      <BottomNav />
    </main>
  );
}
