import { MainLayout } from '@/components/layout/MainLayout';
import { DateRangePicker } from '@/components/ui/date-range-picker';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useApiGet } from '@/hooks/useApiGet';
import { RefreshCw, Filter, RotateCcw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { AlarmStandsResponse } from '@/types';

function toStartOfDayIso(d: Date): string {
  const dt = new Date(d);
  dt.setHours(0, 0, 0, 0);
  return dt.toISOString();
}

function toEndOfDayIso(d: Date): string {
  const dt = new Date(d);
  dt.setHours(23, 59, 59, 999);
  return dt.toISOString();
}

function fmtDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return new Intl.DateTimeFormat('ru-RU', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(d);
}

export default function AlarmAnalysis() {
  const [draftRange, setDraftRange] = useState<DateRange | undefined>(() => {
    const now = new Date();
    const from = new Date(now);
    from.setDate(from.getDate() - 1);
    return { from, to: now };
  });
  const [appliedRange, setAppliedRange] = useState<DateRange | undefined>(draftRange);

  const [draftQuery, setDraftQuery] = useState<string>('');
  const [appliedQuery, setAppliedQuery] = useState<string>('');

  const path = useMemo(() => {
    const params = new URLSearchParams();
    if (appliedRange?.from) params.set('dateFrom', toStartOfDayIso(appliedRange.from));
    if (appliedRange?.to) params.set('dateTo', toEndOfDayIso(appliedRange.to));
    if (appliedQuery.trim()) params.set('q', appliedQuery.trim());
    params.set('limit', '200');
    const qs = params.toString();
    return `/analytics/alarms/stands${qs ? `?${qs}` : ''}`;
  }, [appliedRange?.from, appliedRange?.to, appliedQuery]);

  const {
    data,
    isLoading,
    error,
    refetch,
  } = useApiGet<AlarmStandsResponse>(path, { snapshotAt: null, rows: [] });

  // Polling: refresh periodically.
  useEffect(() => {
    const id = window.setInterval(() => {
      refetch();
    }, 10_000);
    return () => window.clearInterval(id);
  }, [refetch]);

  return (
    <MainLayout title="Анализ тревог" subtitle="Объекты из Стэндов и статистика по архиву">
      <div className="space-y-4 animate-fade-in">
        <Card className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Период:</span>
              <DateRangePicker
                value={draftRange}
                onChange={setDraftRange}
                placeholder="Период"
                triggerClassName="w-[340px]"
                numberOfMonths={2}
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Поиск:</span>
              <Input
                value={draftQuery}
                onChange={(e) => setDraftQuery(e.target.value)}
                placeholder="Panel_id / объект / адрес"
                className="w-[280px] bg-background"
              />
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                className="gap-2"
                onClick={() => {
                  setAppliedRange(draftRange);
                  setAppliedQuery(draftQuery);
                }}
              >
                <Filter className="h-4 w-4" />
                Применить
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="gap-2"
                onClick={() => {
                  const now = new Date();
                  const from = new Date(now);
                  from.setDate(from.getDate() - 1);
                  const next = { from, to: now } as DateRange;
                  setDraftRange(next);
                  setAppliedRange(next);
                  setDraftQuery('');
                  setAppliedQuery('');
                }}
              >
                <RotateCcw className="h-4 w-4" />
                Сбросить
              </Button>
              <Button variant="outline" size="sm" className="gap-2" onClick={refetch}>
                <RefreshCw className="h-4 w-4" />
                Обновить
              </Button>
            </div>

            <div className="ml-auto text-xs text-muted-foreground">
              Обновление: каждые 10 сек · Снимок: {data?.snapshotAt ? fmtDateTime(data.snapshotAt) : '—'}
            </div>
          </div>
          {error ? <div className="mt-2 text-sm text-destructive">{error}</div> : null}
        </Card>

        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="whitespace-nowrap">Panel_id</TableHead>
                <TableHead>Объект / адрес</TableHead>
                <TableHead className="whitespace-nowrap">Долбит (код)</TableHead>
                <TableHead className="whitespace-nowrap text-right">Раз</TableHead>
                <TableHead className="whitespace-nowrap text-right">Событий</TableHead>
                <TableHead className="whitespace-nowrap">Последнее</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.rows || []).map((r) => (
                <TableRow key={r.panelId}>
                  <TableCell className="font-mono whitespace-nowrap">{r.panelId || '—'}</TableCell>
                  <TableCell>
                    <div className="text-foreground">{r.objectName || '—'}</div>
                    <div className="text-xs text-muted-foreground">{r.address || ''}</div>
                  </TableCell>
                  <TableCell className="max-w-[420px]">
                    <div className="space-y-0.5">
                      <div className="font-mono text-xs text-muted-foreground">{r.topCode || '—'}</div>
                      <div className="text-sm text-foreground truncate" title={r.topCodeText || ''}>
                        {r.topCodeText || '—'}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{(r.topCodeCount ?? 0).toLocaleString('ru-RU')}</TableCell>
                  <TableCell className="text-right tabular-nums">{(r.eventsCount ?? 0).toLocaleString('ru-RU')}</TableCell>
                  <TableCell className="whitespace-nowrap">{fmtDateTime(r.lastEventAt)}</TableCell>
                </TableRow>
              ))}
              {!isLoading && (data?.rows || []).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-6 text-sm text-muted-foreground">
                    Нет данных. Проверьте доступ к MSSQL и наличие активных записей в dbo.Stands.
                  </TableCell>
                </TableRow>
              ) : null}
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-6 text-sm text-muted-foreground">
                    Загрузка…
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </div>
    </MainLayout>
  );
}
