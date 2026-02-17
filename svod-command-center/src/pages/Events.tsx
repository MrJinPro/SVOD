import { MainLayout } from '@/components/layout/MainLayout';
import { EventFilters, type EventFiltersValue } from '@/components/events/EventFilters';
import { EventsTable } from '@/components/events/EventsTable';
import { useApiGet } from '@/hooks/useApiGet';
import { Button } from '@/components/ui/button';
import { Download, RefreshCw } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import { useMemo, useState } from 'react';
import { API_BASE_URL } from '@/lib/api';
import { useEventStream } from '@/hooks/useEventStream';
import { EventDetailsSheet } from '@/components/events/EventDetailsSheet.tsx';
import { PaginationBar } from '@/components/PaginationBar';
import type { Event } from '@/types';

const defaultFilters: EventFiltersValue = {
  search: '',
  type: 'all',
  severity: 'all',
  status: 'all',
  todayOnly: false,
  dateRange: { from: null, to: null },
};

function toLocalIso(dt: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
}

export default function Events() {
  const [draftFilters, setDraftFilters] = useState<EventFiltersValue>(defaultFilters);
  const [appliedFilters, setAppliedFilters] = useState<EventFiltersValue>(defaultFilters);
  const [pageNumber, setPageNumber] = useState(1);
  const [live, setLive] = useState(false);
  const [pendingNew, setPendingNew] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

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
      params.set('dateFrom', toLocalIso(start));
      params.set('dateTo', toLocalIso(end));
    } else if (appliedFilters.dateRange.from || appliedFilters.dateRange.to) {
      const from = appliedFilters.dateRange.from ?? appliedFilters.dateRange.to;
      const to = appliedFilters.dateRange.to ?? appliedFilters.dateRange.from;
      if (from && to) {
        const start = new Date(from.getFullYear(), from.getMonth(), from.getDate(), 0, 0, 0, 0);
        const end = new Date(to.getFullYear(), to.getMonth(), to.getDate(), 23, 59, 59, 999);
        params.set('dateFrom', toLocalIso(start));
        params.set('dateTo', toLocalIso(end));
      }
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

  const newestTimestamp = useMemo(() => {
    const first = (page as any)?.data?.[0]?.timestamp;
    return typeof first === 'string' && first ? first : null;
  }, [page]);

  const streamPath = useMemo(() => {
    const params = new URLSearchParams();
    if (newestTimestamp) params.set('since', newestTimestamp);
    params.set('pollSeconds', '1.0');
    return `/events/stream?${params.toString()}`;
  }, [newestTimestamp]);

  useEventStream({
    enabled: live,
    path: streamPath,
    onEvent: (evt) => {
      if (evt.event !== 'event') return;
      setPendingNew((n) => n + 1);
    },
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
            <Button
              variant={live ? 'secondary' : 'outline'}
              size="sm"
              onClick={() => {
                setLive((v) => !v);
                setPendingNew(0);
              }}
              title="Поток новых событий (near real-time)"
            >
              {live ? 'Live: ON' : 'Live: OFF'}
            </Button>
            <Button variant="outline" size="sm" className="gap-2" onClick={refetch}>
              <RefreshCw className="h-4 w-4" />
              Обновить
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => {
                const url = `${API_BASE_URL}/events/export/xlsx?${path.split('?')[1] || ''}`
                  // list endpoint has paging; export endpoint ignores page params safely
                  .replace(/(^|&)page=\d+/g, '$1')
                  .replace(/(^|&)pageSize=\d+/g, '$1')
                  .replace(/[?&]$/g, '');

                toast({ title: 'Экспорт', description: 'Скачивание XLSX…' });
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

        {pendingNew > 0 && (
          <div className="rounded-xl border border-border bg-card p-3 flex items-center justify-between">
            <div className="text-sm text-foreground">
              Появились новые события: <strong>{pendingNew}</strong>
            </div>
            <Button
              size="sm"
              className="gap-2"
              onClick={() => {
                refetch();
                setPendingNew(0);
                toast({ title: 'События', description: 'Обновлено.' });
              }}
            >
              Показать
            </Button>
          </div>
        )}

        {error && (
          <div className="text-sm text-destructive">
            Ошибка загрузки: {error}
          </div>
        )}

        <PaginationBar
          isLoading={isLoading}
          shown={page.data.length}
          total={page.total}
          page={pageNumber}
          totalPages={page.totalPages}
          onPageChange={(next) => setPageNumber(next)}
        />

        {/* Table */}
        <EventsTable
          events={page.data}
          onViewEvent={(evt) => {
            setSelectedEvent(evt);
            setDetailsOpen(true);
          }}
        />

        <EventDetailsSheet
          open={detailsOpen}
          onOpenChange={setDetailsOpen}
          event={selectedEvent}
        />

        <PaginationBar
          isLoading={isLoading}
          shown={page.data.length}
          total={page.total}
          page={pageNumber}
          totalPages={page.totalPages}
          onPageChange={(next) => setPageNumber(next)}
        />
      </div>
    </MainLayout>
  );
}
