import { Bot, Home, Search, Theater, UserRound } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const items = [
  { label: '首页', href: '/home', Icon: Home },
  { label: '剧场', href: '/theater', Icon: Theater },
  { label: '搜索', href: '/search', Icon: Search },
  { label: 'AI', href: '/ai', Icon: Bot },
  { label: '我的', href: '/profile', Icon: UserRound },
];

export default function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-1/2 z-50 flex w-full max-w-[430px] -translate-x-1/2 items-center justify-around border-t border-white/10 bg-background/85 px-3 pb-5 pt-2 backdrop-blur-2xl">
      {items.map(({ label, href, Icon }) => (
        <NavLink
          key={label}
          to={href}
          className={({ isActive }) =>
            `flex min-w-12 flex-col items-center gap-1 rounded-xl px-2 py-1 text-[11px] transition ${
              isActive ? 'text-primary' : 'text-on-surface-variant'
            }`
          }
        >
          <Icon size={20} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
