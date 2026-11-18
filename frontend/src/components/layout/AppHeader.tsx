type PageId = 'home' | 'requirements' | 'test-cases'

type AppHeaderProps = {
  current: PageId
  onNavigate: (page: PageId) => void
}

const LINKS: Array<{ id: PageId; label: string }> = [
  { id: 'home', label: 'Home' },
  { id: 'requirements', label: 'Requirement Analysis' },
  { id: 'test-cases', label: 'Test Case Generation' },
]

export function AppHeader({ current, onNavigate }: AppHeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
        <button
          type="button"
          onClick={() => onNavigate('home')}
          className="text-left text-sm font-semibold tracking-tight text-slate-900"
        >
          AI QA Agent POC
        </button>
        <nav className="flex flex-wrap gap-2" aria-label="Primary">
          {LINKS.map((link) => {
            const active = link.id === current
            return (
              <button
                key={link.id}
                type="button"
                onClick={() => onNavigate(link.id)}
                aria-current={active ? 'page' : undefined}
                className={`rounded-md px-3 py-1.5 text-sm ${
                  active
                    ? 'bg-slate-900 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {link.label}
              </button>
            )
          })}
        </nav>
      </div>
    </header>
  )
}

export type { PageId }
