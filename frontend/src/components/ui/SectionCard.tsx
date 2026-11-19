import type { ReactNode } from 'react'

type SectionCardProps = {
  title: string
  children: ReactNode
  action?: ReactNode
}

export function SectionCard({ title, children, action }: SectionCardProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          {title}
        </h2>
        {action ?? null}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  )
}
