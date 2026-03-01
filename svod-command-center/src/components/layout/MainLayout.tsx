import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { presencePing } from '@/lib/presence';

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

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      try {
        await presencePing();
      } catch {
        // ignore: presence is best-effort
      }
    };

    // First ping right away, then every minute.
    tick();
    const id = window.setInterval(() => {
      if (cancelled) return;
      void tick();
    }, 60_000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar collapsed={collapsed} onToggleCollapsed={() => setCollapsed((v) => !v)} />
      <div className={(collapsed ? 'pl-16' : 'pl-64') + ' transition-all duration-300'}>
        <Header title={title} subtitle={subtitle} />
        <main className="p-6">
          {children}
        </main>
        <footer className="border-t border-border px-6 py-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm">
              <Link
                to="/help"
                className="text-foreground hover:underline underline-offset-4"
              >
                Инструкция
              </Link>
            </div>
            <div className="text-xs text-muted-foreground">
              Разработал MrJinPro · Telegram:{' '}
              <a
                href="https://t.me/mrjinpro"
                target="_blank"
                rel="noreferrer"
                className="hover:underline underline-offset-4"
              >
                @mrjinpro
              </a>
              {' '}· Почта:{' '}
              <a
                href="mailto:dev@mrjin.pro"
                className="hover:underline underline-offset-4"
              >
                dev@mrjin.pro
              </a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
