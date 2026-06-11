import { ChevronLeft, MoreHorizontal, Share2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

type TopBarProps = {
  title?: string;
};

export default function TopBar({ title }: TopBarProps) {
  const navigate = useNavigate();
  const [message, setMessage] = useState<string | null>(null);

  const share = async () => {
    const data = {
      title: title || '互动短剧',
      text: title || '打开互动短剧体验',
      url: window.location.href,
    };
    try {
      if (navigator.share) {
        await navigator.share(data);
      } else {
        await navigator.clipboard.writeText(data.url);
        setMessage('链接已复制');
      }
    } catch {
      setMessage('分享已取消');
    }
  };

  return (
    <header className="fixed left-1/2 top-0 z-50 flex h-14 w-full max-w-[430px] -translate-x-1/2 items-center justify-between bg-background/35 px-margin-page backdrop-blur-xl">
      <button className="icon-button justify-self-start" type="button" aria-label="返回" onClick={() => navigate(-1)}>
        <ChevronLeft size={28} strokeWidth={2.2} />
      </button>
      {title ? <strong className="max-w-48 truncate text-label-md font-semibold">{title}</strong> : null}
      <div className="flex items-center gap-2">
        <button className="icon-button" type="button" aria-label="分享" onClick={share}>
          <Share2 size={20} />
        </button>
        <button className="icon-button" type="button" aria-label="更多" onClick={() => setMessage('更多操作待后续开放')}>
          <MoreHorizontal size={22} />
        </button>
      </div>
      {message ? (
        <div className="absolute right-margin-page top-12 rounded-xl bg-surface-container-high px-3 py-2 text-label-md text-on-surface shadow-lg">
          {message}
        </div>
      ) : null}
    </header>
  );
}
