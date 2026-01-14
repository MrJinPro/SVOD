import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useEffect, useState } from 'react';

interface MainLayoutProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
}

export function MainLayout({ children, title, subtitle }: MainLayoutProps) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem('svod_sidebar_collapsed') === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('svod_sidebar_collapsed', collapsed ? '1' : '0');
    } catch {
      // ignore
    }
  }, [collapsed]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar collapsed={collapsed} onToggleCollapsed={() => setCollapsed((v) => !v)} />
      <div className={(collapsed ? 'pl-16' : 'pl-64') + ' transition-all duration-300'}>
        <Header title={title} subtitle={subtitle} />
        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
