import { Bell, ChevronRight, Clock3, Download, Heart, Settings, Star } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { ErrorState, LoadingState } from '../components/PageState';
import { loadProfile } from '../data/profile';
import type { UserProfile } from '../data/profile';

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProfile(await loadProfile());
    } catch (err) {
      setError(err instanceof Error ? err.message : '用户资料加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (loading) return <LoadingState title="正在加载我的资料" />;
  if (error || !profile) return <ErrorState title="我的页面不可用" message={error || '用户资料为空'} onAction={reload} />;

  const stats = [
    { label: '已看', value: `${profile.stats.watchedEpisodes}集` },
    { label: '互动', value: `${profile.stats.interactions}次` },
    { label: '收藏', value: `${profile.stats.favorites}部` },
  ];

  const continueWatching = profile.continueWatching || { dramaId: '', episodeNumber: 1, title: '暂无观看记录' };
  const menuItems = [
    {
      label: '继续观看',
      sub: continueWatching.title,
      Icon: Clock3,
      href: `/player?drama=${continueWatching.dramaId}&episode=${continueWatching.episodeNumber}`,
    },
    { label: '我的收藏', sub: `${profile.stats.favorites} 部短剧`, Icon: Heart, href: '/theater' },
    { label: '互动记录', sub: `${profile.stats.interactions} 次互动`, Icon: Star, href: '/theater' },
    { label: '离线缓存', sub: '功能待后续阶段开放', Icon: Download, href: '/theater' },
  ];

  return (
    <main className="phone-safe min-h-dvh pb-24 pt-5">
      <header className="flex items-center justify-between px-margin-page pb-5">
        <h1 className="text-display-lg font-bold">我的</h1>
        <div className="flex gap-2">
          <button className="icon-button glass-panel" type="button" aria-label="通知" onClick={() => setNotice('暂无新通知')}>
            <Bell size={19} />
          </button>
          <button className="icon-button glass-panel" type="button" aria-label="设置" onClick={() => setNotice('设置功能待后续开放')}>
            <Settings size={19} />
          </button>
        </div>
      </header>

      <section className="px-margin-page">
        <div className="glass-panel rounded-2xl p-4">
          <div className="mb-4 flex items-center gap-3">
            <div className="grid h-16 w-16 place-items-center rounded-2xl bg-primary-container text-xl font-bold text-white">{profile.avatarText}</div>
            <div>
              <h2 className="text-headline-md font-bold">{profile.displayName}</h2>
              <p className="text-body-sm text-on-surface-variant">{profile.bio}</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {stats.map((item) => (
              <div key={item.label} className="rounded-2xl bg-white/6 p-3 text-center">
                <strong className="block text-body-lg">{item.value}</strong>
                <span className="text-label-md text-on-surface-variant">{item.label}</span>
              </div>
            ))}
          </div>
          {notice ? <p className="mt-3 rounded-xl bg-white/6 px-3 py-2 text-label-md text-on-surface-variant">{notice}</p> : null}
        </div>
      </section>

      <section className="space-y-3 px-margin-page py-stack-lg">
        {menuItems.map(({ label, sub, Icon, href }) => (
          <Link key={label} className="glass-panel flex items-center gap-3 rounded-2xl p-4" to={href}>
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/8 text-primary">
              <Icon size={19} />
            </span>
            <span className="min-w-0 flex-1">
              <strong className="block text-body-lg">{label}</strong>
              <span className="text-label-md text-on-surface-variant">{sub}</span>
            </span>
            <ChevronRight size={18} className="text-on-surface-variant" />
          </Link>
        ))}
      </section>

      <BottomNav />
    </main>
  );
}
