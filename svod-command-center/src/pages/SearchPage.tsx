import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, X } from 'lucide-react';

import { MainLayout } from '@/components/layout/MainLayout';
import { EventsTable } from '@/components/events/EventsTable';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiGet } from '@/lib/api';
import { SearchObjectResult, UnifiedSearchResponse } from '@/types';

const emptyResults: UnifiedSearchResponse = {
  query: '',
  events: [],
  objects: [],
  total: 0,
};

export default function SearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [hasSearched, setHasSearched] = useState(false);
  const [results, setResults] = useState<UnifiedSearchResponse>(emptyResults);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queryFromUrl = (searchParams.get('q') || '').trim();

  const runSearch = async (nextQuery: string) => {
    const trimmed = nextQuery.trim();
    if (!trimmed) {
      setHasSearched(false);
      setResults(emptyResults);
      setError(null);
      return;
    }

    setHasSearched(true);
    setIsLoading(true);
    setError(null);

    try {
      const payload = await apiGet<UnifiedSearchResponse>(`/search?q=${encodeURIComponent(trimmed)}`);
      setResults(payload);
    } catch (requestError: any) {
      setResults(emptyResults);
      setError(requestError?.message || 'Ошибка запроса');
    } finally {
      setIsLoading(false);
    }
  };

  const submitSearch = (overrideQuery?: string) => {
    const nextQuery = (overrideQuery ?? query).trim();
    if (!nextQuery) {
      handleClear();
      return;
    }

    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('q', nextQuery);
    setSearchParams(nextParams);
  };

  useEffect(() => {
    setQuery(queryFromUrl);
    void runSearch(queryFromUrl);
  }, [queryFromUrl]);

  const handleClear = () => {
    setQuery('');
    setHasSearched(false);
    setResults(emptyResults);
    setError(null);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete('q');
    setSearchParams(nextParams);
  };

  const objectResults: SearchObjectResult[] = results.objects;

  return (
    <MainLayout title="Поиск" subtitle="Умный поиск по событиям и объектам">
      <div className="space-y-6 animate-fade-in">
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    submitSearch();
                  }
                }}
                placeholder="Введите номер, объект, клиента, адрес, комментарий, код или телефон..."
                className="h-12 bg-background pl-12 text-lg"
              />
              {query && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-2 top-1/2 h-8 w-8 -translate-y-1/2"
                  onClick={handleClear}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
            <Button onClick={() => submitSearch()} className="h-12 px-8">
              <Search className="mr-2 h-5 w-5" />
              Поиск
            </Button>
          </div>
        </div>

        {hasSearched && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {isLoading ? (
                  'Поиск…'
                ) : (
                  <>
                    Найдено: <strong className="text-foreground">{results.total}</strong> результатов по запросу «{queryFromUrl || query}»
                  </>
                )}
              </p>
              {!isLoading && (
                <div className="flex items-center gap-2 text-xs">
                  <Badge variant="outline">События: {results.events.length}</Badge>
                  <Badge variant="outline">Объекты: {results.objects.length}</Badge>
                </div>
              )}
            </div>

            {error && <div className="text-sm text-destructive">Ошибка поиска: {error}</div>}

            {results.total > 0 ? (
              <div className="space-y-6">
                {results.events.length > 0 && (
                  <section className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Badge>События</Badge>
                      <span className="text-sm text-muted-foreground">{results.events.length} найдено</span>
                    </div>
                    <EventsTable
                      events={results.events}
                      onViewEvent={(event) => navigate(`/events?openEventId=${encodeURIComponent(event.id)}`)}
                    />
                  </section>
                )}

                {objectResults.length > 0 && (
                  <section className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">Объекты</Badge>
                      <span className="text-sm text-muted-foreground">{objectResults.length} найдено</span>
                    </div>
                    <div className="overflow-hidden rounded-xl border border-border bg-card">
                      <Table>
                        <TableHeader>
                          <TableRow className="border-border hover:bg-transparent">
                            <TableHead className="w-[140px]">ID</TableHead>
                            <TableHead>Название</TableHead>
                            <TableHead>Адрес</TableHead>
                            <TableHead>Клиент</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {objectResults.map((item) => (
                            <TableRow
                              key={item.id}
                              className="table-row-hover cursor-pointer border-border"
                              onClick={() => navigate(`/objects/${encodeURIComponent(item.id)}`)}
                            >
                              <TableCell className="font-mono text-sm">{item.id}</TableCell>
                              <TableCell className="font-medium">{item.name || item.id}</TableCell>
                              <TableCell className="text-muted-foreground">{item.address || '—'}</TableCell>
                              <TableCell>{item.clientName || '—'}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </section>
                )}
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card p-12 text-center">
                <Search className="mx-auto mb-4 h-12 w-12 text-muted-foreground/50" />
                <h3 className="mb-2 text-lg font-medium text-foreground">Ничего не найдено</h3>
                <p className="text-muted-foreground">
                  Попробуйте изменить поисковый запрос или использовать другие ключевые слова
                </p>
              </div>
            )}
          </div>
        )}

        {!hasSearched && (
          <div className="rounded-xl border border-dashed border-border bg-card/50 p-12 text-center">
            <Search className="mx-auto mb-4 h-16 w-16 text-muted-foreground/30" />
            <h3 className="mb-2 text-lg font-medium text-foreground">Начните поиск</h3>
            <p className="mx-auto max-w-md text-muted-foreground">
              Введите ключевые слова для поиска по номеру объекта, клиенту, адресу, описанию события, комментарию оператора или телефону ответственного
            </p>
          </div>
        )}
      </div>
    </MainLayout>
  );
}