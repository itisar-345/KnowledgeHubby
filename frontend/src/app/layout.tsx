import './globals.css'
import ErrorBoundary from '@/components/ErrorBoundary'

export const metadata = {
  title: 'Knowledge Hubs',
  description: 'Team knowledge extraction and curation',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <h1>Knowledge Hubs</h1>
          <div className="nav-links">
            <a href="/knowledge">Hub</a>
          </div>
        </nav>
        <main>
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </body>
    </html>
  )
}
