import { Bell, Search, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useApiGet } from '@/hooks/useApiGet';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [quickQuery, setQuickQuery] = useState('');
  const navigate = useNavigate();
  const { data: notifications } = useApiGet('/notifications', [] as Array<{ id: string; read: boolean }>);
  const unreadCount = notifications.filter((n) => !n.read).length;

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('ru-RU', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Быстрый поиск..."
            className="w-64 pl-9 bg-muted/50 border-muted focus:bg-background"
            value={quickQuery}
            onChange={(e) => setQuickQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const q = quickQuery.trim();
                if (q) navigate(`/search?q=${encodeURIComponent(q)}`);
              }
            }}
          />
        </div>

        {/* Time display */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/50 text-muted-foreground">
          <Clock className="h-4 w-4" />
          <div className="text-sm">
            <span className="font-mono font-medium text-foreground">{formatTime(currentTime)}</span>
            <span className="mx-2 text-muted-foreground/50">|</span>
            <span className="capitalize">{formatDate(currentTime)}</span>
          </div>
        </div>

        {/* Notifications */}
        <Link to="/notifications">
          <Button variant="ghost" size="icon" className="relative">
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <Badge className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center bg-severity-critical text-white text-xs border-2 border-background">
                {unreadCount}
              </Badge>
            )}
          </Button>
        </Link>
      </div>
    </header>
  );
}
