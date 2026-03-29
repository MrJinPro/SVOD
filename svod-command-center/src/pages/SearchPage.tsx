import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { LoaderCircle, Search, X } from 'lucide-react';

import { MainLayout } from '@/components/layout/MainLayout';
import { EventsTable } from '@/components/events/EventsTable';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiGet } from '@/lib/api';
import { ObjectListItem, PaginatedResponse, SearchObjectResult, UnifiedSearchResponse } from '@/types';

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
  const [progressValue, setProgressValue] = useState(0);
  const [progressLabel, setProgressLabel] = useState('');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const requestIdRef = useRef(0);

  const queryFromUrl = (searchParams.get('q') || '').trim();

  useEffect(() => {
    if (!isLoading) {
      setElapsedSeconds(0);
      return;
    }

    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    }, 250);

    return () => window.clearInterval(timer);
  }, [isLoading]);

  const mapObjectPreview = (item: ObjectListItem): SearchObjectResult => ({
    ...item,
    resultType: 'object',
  });

  const runSearch = async (nextQuery: string) => {
    const trimmed = nextQuery.trim();
    const currentRequestId = requestIdRef.current + 1;
    requestIdRef.current = currentRequestId;

    if (!trimmed) {
      setHasSearched(false);
      setResults(emptyResults);
      setError(null);
      setProgressValue(0);
      setProgressLabel('');
      return;
    }

    setHasSearched(true);
    setIsLoading(true);
    setError(null);
    setResults(emptyResults);
    setProgressValue(8);
    setProgressLabel('Сначала быстро ищем объекты в локальной базе…');

    try {
      const objectPreviewParams = new URLSearchParams({
        page: '1',
        pageSize: '8',
        includeDisabled: 'true',
        includeIdPrefix: 'true',
        includeStarPrefix: 'true',
        search: trimmed,
      });

      const previewPayload = await apiGet<PaginatedResponse<ObjectListItem>>(
        `/objects?${objectPreviewParams.toString()}`
      );

      if (requestIdRef.current !== currentRequestId) {
        return;
      }

      const previewObjects = previewPayload.data.map(mapObjectPreview);
      setResults({
        query: trimmed,
        objects: previewObjects,
        events: [],
        total: previewObjects.length,
      });
      setProgressValue(previewObjects.length > 0 ? 45 : 30);
      setProgressLabel(
        previewObjects.length > 0
          ? 'Объекты уже найдены. Продолжаем расширенный поиск по событиям и связанным данным…'
          : 'Быстрых совпадений по объектам пока нет. Продолжаем расширенный поиск…'
      );

      const payload = await apiGet<UnifiedSearchResponse>(`/search?q=${encodeURIComponent(trimmed)}`);

      if (requestIdRef.current !== currentRequestId) {
        return;
      }

      setResults(payload);
      setProgressValue(100);
      setProgressLabel(
        payload.total > 0 ? 'Поиск завершён. Полный результат готов.' : 'Поиск завершён. Совпадения не найдены.'
      );
    } catch (requestError: any) {
      if (requestIdRef.current !== currentRequestId) {
        return;
      }

      setResults(emptyResults);
      setError(requestError?.message || 'Ошибка запроса');
      setProgressValue(100);
      setProgressLabel('Поиск завершился с ошибкой.');
    } finally {
      if (requestIdRef.current === currentRequestId) {
        setIsLoading(false);
      }
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
            {(isLoading || progressLabel) && (
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-sm text-foreground">
                      {isLoading && <LoaderCircle className="h-4 w-4 animate-spin text-primary" />}
                      <span>{progressLabel || 'Подготовка поиска…'}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {isLoading
                        ? `Запрос выполняется ${elapsedSeconds} сек. Сначала показываем объекты, затем дотягиваем события.`
                        : 'Последний этап поиска завершён.'}
                    </p>
                  </div>
                  <div className="min-w-24 text-right text-sm text-muted-foreground">{progressValue}%</div>
                </div>
                <Progress className="mt-3 h-2" value={progressValue} />
              </div>
            )}

            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {isLoading ? (
                  <>
                    Ищем: <strong className="text-foreground">{queryFromUrl || query}</strong>
                  </>
                ) : (
                  <>
                    Найдено: <strong className="text-foreground">{results.total}</strong> результатов по запросу «{queryFromUrl || query}»
                  </>
                )}
              </p>
              {(results.objects.length > 0 || results.events.length > 0) && (
                <div className="flex items-center gap-2 text-xs">
                  <Badge variant="outline">События: {results.events.length}</Badge>
                  <Badge variant="outline">Объекты: {results.objects.length}</Badge>
                </div>
              )}
            </div>

            {error && <div className="text-sm text-destructive">Ошибка поиска: {error}</div>}

            {results.total > 0 ? (
              <div className="space-y-6">
                {objectResults.length > 0 && (
                  <section className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">Объекты</Badge>
                      <span className="text-sm text-muted-foreground">
                        {objectResults.length} {isLoading ? 'показано сразу' : 'найдено'}
                      </span>
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

                {results.events.length > 0 && (
                  <section className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Badge>События</Badge>
                      <span className="text-sm text-muted-foreground">
                        {results.events.length} найдено после расширенного поиска
                      </span>
                    </div>
                    <EventsTable
                      events={results.events}
                      onViewEvent={(event) => navigate(`/events?openEventId=${encodeURIComponent(event.id)}`)}
                    />
                  </section>
                )}
              </div>
            ) : isLoading ? (
              <div className="rounded-xl border border-border bg-card p-12 text-center">
                <LoaderCircle className="mx-auto mb-4 h-12 w-12 animate-spin text-primary/70" />
                <h3 className="mb-2 text-lg font-medium text-foreground">Поиск выполняется</h3>
                <p className="text-muted-foreground">
                  Как только найдём быстрые совпадения по объектам, они появятся здесь сразу, не дожидаясь полного поиска.
                </p>
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