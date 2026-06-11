import type { ReactNode } from 'react';

type SectionTitleProps = {
  children: ReactNode;
  action?: ReactNode;
};

export default function SectionTitle({ children, action }: SectionTitleProps) {
  return (
    <div className="mb-stack-sm flex items-center justify-between px-margin-page">
      <h2 className="text-headline-md font-semibold text-on-surface">{children}</h2>
      {action}
    </div>
  );
}
