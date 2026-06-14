import './globals.css'
import ErrorBoundary from '@/components/ErrorBoundary'
import { AuthProvider } from '@/lib/auth'
import NavBar from '@/components/NavBar'

export const metadata = {
  title: 'Knowledge Hubs',
  description: 'Team knowledge extraction and curation',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <NavBar />
          <main>
            <ErrorBoundary>{children}</ErrorBoundary>
          </main>
        </AuthProvider>
      </body>
    </html>
  )
}
