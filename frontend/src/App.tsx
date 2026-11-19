import { useState } from 'react'
import { AppHeader } from './components/layout/AppHeader'
import type { PageId } from './components/layout/AppHeader'
import { HomePage } from './pages/HomePage'
import { QaExecutionPage } from './pages/QaExecutionPage'
import { QaReviewPage } from './pages/QaReviewPage'
import { RequirementAnalysisPage } from './pages/RequirementAnalysisPage'
import { TestCaseGenerationPage } from './pages/TestCaseGenerationPage'

function App() {
  const [page, setPage] = useState<PageId>('home')

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <AppHeader current={page} onNavigate={setPage} />
      {page === 'home' ? <HomePage /> : null}
      {page === 'requirements' ? (
        <RequirementAnalysisPage onNavigateToTestCases={() => setPage('test-cases')} />
      ) : null}
      {page === 'test-cases' ? (
        <TestCaseGenerationPage onNavigateToQaReview={() => setPage('qa-review')} />
      ) : null}
      {page === 'qa-review' ? <QaReviewPage /> : null}
      {page === 'qa-execution' ? <QaExecutionPage /> : null}
    </div>
  )
}

export default App
