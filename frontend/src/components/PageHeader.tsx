import React from "react";

interface PageHeaderProps {
  title: string;
  badge?: string;
  description: string;
  actions?: React.ReactNode;
}

export function PageHeader({ title, badge, description, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
      <div>
        <div className="flex items-center space-x-2.5">
          <h1 className="text-2xl font-bold tracking-tight text-white">{title}</h1>
          {badge && (
            <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-xs font-semibold text-blue-400 border border-blue-500/20">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-slate-400">{description}</p>
      </div>
      {actions && <div className="flex items-center space-x-2 shrink-0">{actions}</div>}
    </div>
  );
}

