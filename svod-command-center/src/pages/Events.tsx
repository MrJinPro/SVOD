import { MainLayout } from '@/components/layout/MainLayout';
import { EventFilters, type EventFiltersValue } from '@/components/events/EventFilters';
import { EventsTable } from '@/components/events/EventsTable';
import { useApiGet } from '@/hooks/useApiGet';
import { Button } from '@/components/ui/button';
import { Download, RefreshCw } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import { useMemo, useState } from 'react';
import { API_BASE_URL } from '@/lib/api';

const defaultFilters: EventFiltersValue = {
  search: '',
  type: 'all',
  severity: 'all',
  status: 'all',
  todayOnly: false,
};

export default function Events() {
  const [draftFilters, setDraftFilters] = useState<EventFiltersValue>(defaultFilters);
  const [appliedFilters, setAppliedFilters] = useState<EventFiltersValue>(defaultFilters);
  const [pageNumber, setPageNumber] = useState(1);

  const path = useMemo(() => {
    const params = new URLSearchParams();
    params.set('page', String(pageNumber));
    params.set('pageSize', '50');

    if (appliedFilters.search.trim()) params.set('search', appliedFilters.search.trim());
    if (appliedFilters.type !== 'all') params.set('type', appliedFilters.type);
    if (appliedFilters.severity !== 'all') params.set('severity', appliedFilters.severity);
    if (appliedFilters.status !== 'all') params.set('status', appliedFilters.status);

    if (appliedFilters.todayOnly) {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
      const end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
      params.set('dateFrom', start.toISOString());
      params.set('dateTo', end.toISOString());
    }

    return `/events?${params.toString()}`;
  }, [appliedFilters, pageNumber]);

  const { data: page, refetch, error, isLoading } = useApiGet(path, {
    data: [],
    total: 0,
    page: 1,
    pageSize: 50,
    totalPages: 1,
  });

  return (
    <MainLayout 
      title="События" 
      subtitle="Журнал событий охраняемых объектов"
    >
      <div className="space-y-4 animate-fade-in">
        {/* Actions bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Найдено: <strong className="text-foreground">{page.total}</strong> событий</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2" onClick={refetch}>
              <RefreshCw className="h-4 w-4" />
              Обновить
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => {
                const url = `${API_BASE_URL}/events/export?${path.split('?')[1] || ''}`
                  // list endpoint has paging; export endpoint ignores page params safely
                  .replace(/(^|&)page=\d+/g, '$1')
                  .replace(/(^|&)pageSize=\d+/g, '$1')
                  .replace(/[?&]$/g, '');

                toast({ title: 'Экспорт', description: 'Скачивание CSV…' });
                window.location.href = url;
              }}
            >
              <Download className="h-4 w-4" />
              Экспорт
            </Button>
          </div>
        </div>

        {/* Filters */}
        <EventFilters
          value={draftFilters}
          onChange={setDraftFilters}
          onApply={() => {
            setAppliedFilters(draftFilters);
            setPageNumber(1);
          }}
          onReset={() => {
            setDraftFilters(defaultFilters);
            setAppliedFilters(defaultFilters);
            setPageNumber(1);
          }}
        />

        {error && (
          <div className="text-sm text-destructive">
            Ошибка загрузки: {error}
          </div>
        )}

        {/* Table */}
        <EventsTable events={page.data} />

        {/* Pagination */}
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {isLoading ? 'Загрузка…' : `Показано ${page.data.length} из ${page.total}`}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pageNumber <= 1}
              onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            >
              Назад
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pageNumber >= page.totalPages}
              onClick={() => setPageNumber((p) => Math.min(page.totalPages, p + 1))}
            >
              Вперёд
            </Button>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
