import { Search, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [quickQuery, setQuickQuery] = useState('');
  const navigate = useNavigate();

  const submitQuickSearch = () => {
    const q = quickQuery.trim();
    if (!q) return;
    navigate(`/search?q=${encodeURIComponent(q)}`);
  };

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
        <div className="hidden md:flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Поиск по объектам и событиям..."
              className="w-72 pl-9 bg-muted/50 border-muted focus:bg-background"
              value={quickQuery}
              onChange={(e) => setQuickQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  submitQuickSearch();
                }
              }}
            />
          </div>
          <Button variant="outline" size="sm" onClick={submitQuickSearch}>Найти</Button>
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

      </div>
    </header>
  );
}
