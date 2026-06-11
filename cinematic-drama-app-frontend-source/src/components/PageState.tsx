import { RefreshCw } from 'lucide-react';

type PageStateProps = {
  title: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function LoadingState({ title = '加载中' }: Partial<PageStateProps>) {
  return (
    <div className="phone-safe flex min-h-dvh items-center justify-center px-margin-page text-center">
      <div className="w-full rounded-2xl border border-white/8 bg-white/5 p-5">
        <div className="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <h1 className="text-headline-md font-semibold text-on-surface">{title}</h1>
      </div>
    </div>
  );
}

export function ErrorState({ title, message, actionLabel = '重试', onAction }: PageStateProps) {
  return (
    <div className="phone-safe flex min-h-dvh items-center justify-center px-margin-page text-center">
      <div className="w-full rounded-2xl border border-error/30 bg-error/10 p-5">
        <h1 className="mb-2 text-headline-md font-semibold text-on-surface">{title}</h1>
        {message ? <p className="mb-4 text-body-sm text-on-surface-variant">{message}</p> : null}
        {onAction ? (
          <button
            className="mx-auto flex h-11 items-center justify-center gap-2 rounded-xl bg-white/10 px-4 text-body-sm text-on-surface"
            type="button"
            onClick={onAction}
          >
            <RefreshCw size={16} />
            {actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function EmptyState({ title, message }: Pick<PageStateProps, 'title' | 'message'>) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-6 text-center">
      <h2 className="text-body-lg font-semibold text-on-surface">{title}</h2>
      {message ? <p className="mt-1 text-body-sm text-on-surface-variant">{message}</p> : null}
    </div>
  );
}
