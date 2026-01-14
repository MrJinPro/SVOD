import { useState } from 'react';
import { MainLayout } from '@/components/layout/MainLayout';
import { EventsTable } from '@/components/events/EventsTable';
import { apiGet } from '@/lib/api';
import { Event } from '@/types';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, X } from 'lucide-react';
import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [hasSearched, setHasSearched] = useState(false);

  const [results, setResults] = useState<Event[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (overrideQuery?: string) => {
    const q = (overrideQuery ?? query).trim();
    if (!q) return;

    setHasSearched(true);
    setIsLoading(true);
    setError(null);
    try {
      const items = await apiGet<Event[]>(`/search/events?q=${encodeURIComponent(q)}`);
      setResults(items);
    } catch (e: any) {
      setResults([]);
      setError(e?.message || 'Ошибка запроса');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const q = (searchParams.get('q') || '').trim();
    if (q) {
      setQuery(q);
      handleSearch(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleClear = () => {
    setQuery('');
    setHasSearched(false);
    setResults([]);
    setError(null);
  };

  return (
    <MainLayout 
      title="Поиск" 
      subtitle="Полнотекстовый поиск по событиям"
    >
      <div className="space-y-6 animate-fade-in">
        {/* Search bar */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Введите поисковый запрос (описание, объект, клиент, локация)..."
                className="pl-12 h-12 text-lg bg-background"
              />
              {query && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8"
                  onClick={handleClear}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
            <Button onClick={handleSearch} className="h-12 px-8">
              <Search className="h-5 w-5 mr-2" />
              Поиск
            </Button>
          </div>
        </div>

        {/* Results */}
        {hasSearched && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {isLoading
                  ? 'Поиск…'
                  : (
                    <>Найдено: <strong className="text-foreground">{results.length}</strong> событий по запросу «{query}»</>
                  )}
              </p>
            </div>

            {error && (
              <div className="text-sm text-destructive">Ошибка поиска: {error}</div>
            )}

            {results.length > 0 ? (
              <EventsTable events={results} />
            ) : (
              <div className="rounded-xl border border-border bg-card p-12 text-center">
                <Search className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                <h3 className="text-lg font-medium text-foreground mb-2">Ничего не найдено</h3>
                <p className="text-muted-foreground">
                  Попробуйте изменить поисковый запрос или использовать другие ключевые слова
                </p>
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {!hasSearched && (
          <div className="rounded-xl border border-dashed border-border bg-card/50 p-12 text-center">
            <Search className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">Начните поиск</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              Введите ключевые слова для поиска по описанию событий, названию объекта, клиенту или локации
            </p>
          </div>
        )}
      </div>
    </MainLayout>
  );
}
