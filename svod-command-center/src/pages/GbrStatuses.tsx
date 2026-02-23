import { MainLayout } from '@/components/layout/MainLayout';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DateRangePicker } from '@/components/ui/date-range-picker';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useApiGet } from '@/hooks/useApiGet';
import { RefreshCw, Filter, RotateCcw } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { GbrArchiveTripsResponse, GbrGroupStatusesResponse } from '@/types';
import type { DateRange } from 'react-day-picker';

type HistoryDraft = {
  dateFrom: string; // YYYY-MM-DD
  dateTo: string; // YYYY-MM-DD
  groupId: string;
  panelId: string;
  limit: string;
};

const defaultHistoryDraft: HistoryDraft = {
  dateFrom: '',
  dateTo: '',
  groupId: '',
  panelId: '',
  limit: '200',
};

function toStartOfDayIso(date: string): string {
  return new Date(`${date}T00:00:00`).toISOString();
}

function toEndOfDayIso(date: string): string {
  return new Date(`${date}T23:59:59.999`).toISOString();
}

function formatLocalYYYYMMDD(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function parseLocalYYYYMMDD(s: string): Date | undefined {
  const trimmed = (s || '').trim();
  if (!trimmed) return undefined;
  const m = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(trimmed);
  if (!m) return undefined;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (!Number.isFinite(y) || !Number.isFinite(mo) || !Number.isFinite(d)) return undefined;
  return new Date(y, mo - 1, d);
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

function fmtDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function GbrStatuses() {
  const {
    data: current,
    isLoading: currentLoading,
    error: currentError,
    refetch: refetchCurrent,
  } = useApiGet<GbrGroupStatusesResponse>('/analytics/gbr/statuses', {
    snapshotAt: '',
    rows: [],
  });

  const [draft, setDraft] = useState<HistoryDraft>(defaultHistoryDraft);
  const [applied, setApplied] = useState<HistoryDraft>(defaultHistoryDraft);

  const historyPath = useMemo(() => {
    const params = new URLSearchParams();

    if (applied.dateFrom) params.set('dateFrom', toStartOfDayIso(applied.dateFrom));
    if (applied.dateTo) params.set('dateTo', toEndOfDayIso(applied.dateTo));
    if (applied.groupId.trim()) params.set('groupId', applied.groupId.trim());
    if (applied.panelId.trim()) params.set('panelId', applied.panelId.trim());

    const parsedLimit = Number(applied.limit);
    const limit = Number.isFinite(parsedLimit) && parsedLimit > 0 ? Math.min(5000, parsedLimit) : 200;
    params.set('limit', String(limit));

    return `/analytics/gbr/archive-trips?${params.toString()}`;
  }, [applied]);

  const {
    data: history,
    isLoading: historyLoading,
    error: historyError,
    refetch: refetchHistory,
  } = useApiGet<GbrArchiveTripsResponse>(historyPath, {
    snapshotAt: '',
    rows: [],
  });

  const forbiddenHint = useMemo(() => {
    const combined = [currentError, historyError].filter(Boolean).join(' | ').toLowerCase();
    if (!combined) return null;
    if (combined.includes('missing permissions') || combined.includes('forbidden')) {
      return 'Нет доступа: требуется право analytics:read (роль admin/analyst).';
    }
    return null;
  }, [currentError, historyError]);

  return (
    <MainLayout title="Статусы ГБР" subtitle="Текущие статусы групп и история (ArchiveGroupResponse)">
      <div className="space-y-4 animate-fade-in">
        {forbiddenHint ? (
          <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
            {forbiddenHint}
          </div>
        ) : null}

        <Tabs defaultValue="current">
          <TabsList>
            <TabsTrigger value="current">Текущие</TabsTrigger>
            <TabsTrigger value="history">История</TabsTrigger>
          </TabsList>

          <TabsContent value="current">
            <Card className="p-4">
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="outline" size="sm" className="gap-2" onClick={refetchCurrent}>
                  <RefreshCw className="h-4 w-4" />
                  Обновить
                </Button>
                <div className="text-sm text-muted-foreground">
                  Снимок: {current?.snapshotAt ? fmtDateTime(current.snapshotAt) : '—'}
                </div>
                <div className="text-sm text-muted-foreground">Строк: {current?.rows?.length ?? 0}</div>
                {currentLoading ? (
                  <div className="text-sm text-muted-foreground">Загрузка…</div>
                ) : null}
                {currentError && !forbiddenHint ? (
                  <div className="text-sm text-destructive">{currentError}</div>
                ) : null}
              </div>

              <div className="mt-4 rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="whitespace-nowrap">Группа</TableHead>
                      <TableHead className="whitespace-nowrap">ГБР</TableHead>
                      <TableHead className="whitespace-nowrap">Статус</TableHead>
                      <TableHead className="whitespace-nowrap">Объект (Panel_id)</TableHead>
                      <TableHead className="whitespace-nowrap">Позывной</TableHead>
                      <TableHead className="whitespace-nowrap">С</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(current?.rows || []).map((r) => (
                      <TableRow key={String(r.Group_id)}>
                        <TableCell className="whitespace-nowrap">{r.Group_id}</TableCell>
                        <TableCell className="min-w-[220px]">{r.Description || '—'}</TableCell>
                        <TableCell className="min-w-[200px]">
                          {r.StatusReason || (r.Status_id !== null ? `#${r.Status_id}` : '—')}
                        </TableCell>
                        <TableCell className="whitespace-nowrap">{r.Panel_id || '—'}</TableCell>
                        <TableCell className="whitespace-nowrap">{r.callsign || '—'}</TableCell>
                        <TableCell className="whitespace-nowrap">{fmtDateTime(r.StartTime)}</TableCell>
                      </TableRow>
                    ))}
                    {!currentLoading && (current?.rows || []).length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-sm text-muted-foreground">
                          Нет данных. Проверьте, что в `agency_raw.db` есть таблицы `GroupResponse` и `StatusGroupResponse`.
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </TableBody>
                </Table>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="history">
            <div className="space-y-4">
              <Card className="p-4">
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Период:</span>
                    <DateRangePicker
                      value={(() => {
                        const from = parseLocalYYYYMMDD(draft.dateFrom);
                        const to = parseLocalYYYYMMDD(draft.dateTo);
                        if (!from && !to) return undefined;
                        return { from, to } as DateRange;
                      })()}
                      onChange={(range) => {
                        setDraft((v) => ({
                          ...v,
                          dateFrom: range?.from ? formatLocalYYYYMMDD(range.from) : '',
                          dateTo: range?.to ? formatLocalYYYYMMDD(range.to) : '',
                        }));
                      }}
                      placeholder="Период"
                      triggerClassName="w-[340px]"
                      numberOfMonths={2}
                    />
                  </div>

                  <Input
                    className="w-[140px] bg-background"
                    placeholder="Group_id"
                    value={draft.groupId}
                    onChange={(e) => setDraft((v) => ({ ...v, groupId: e.target.value }))}
                  />
                  <Input
                    className="w-[180px] bg-background"
                    placeholder="Panel_id"
                    value={draft.panelId}
                    onChange={(e) => setDraft((v) => ({ ...v, panelId: e.target.value }))}
                  />
                  <Input
                    className="w-[120px] bg-background"
                    placeholder="Limit"
                    value={draft.limit}
                    onChange={(e) => setDraft((v) => ({ ...v, limit: e.target.value }))}
                  />

                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="gap-2"
                      onClick={() => setApplied(draft)}
                    >
                      <Filter className="h-4 w-4" />
                      Применить
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="gap-2"
                      onClick={() => {
                        setDraft(defaultHistoryDraft);
                        setApplied(defaultHistoryDraft);
                      }}
                    >
                      <RotateCcw className="h-4 w-4" />
                      Сбросить
                    </Button>
                    <Button variant="outline" size="sm" className="gap-2" onClick={refetchHistory}>
                      <RefreshCw className="h-4 w-4" />
                      Обновить
                    </Button>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                  <div>Снимок: {history?.snapshotAt ? fmtDateTime(history.snapshotAt) : '—'}</div>
                  <div>Строк: {history?.rows?.length ?? 0}</div>
                  {historyLoading ? <div>Загрузка…</div> : null}
                  {historyError && !forbiddenHint ? <div className="text-destructive">{historyError}</div> : null}
                </div>
              </Card>

              <Card className="p-0">
                <div className="rounded-lg border border-border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="whitespace-nowrap">Старт</TableHead>
                        <TableHead className="whitespace-nowrap">Финиш</TableHead>
                        <TableHead className="whitespace-nowrap">Длительность</TableHead>
                        <TableHead className="whitespace-nowrap">ГБР</TableHead>
                        <TableHead className="whitespace-nowrap">Статус</TableHead>
                        <TableHead className="whitespace-nowrap">Объект</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(history?.rows || []).map((r) => {
                        const obj = (r.ObjectName || r.Panel_id || '—') as string;
                        const status = r.StatusReason || (r.Status_id !== null ? `#${r.Status_id}` : '—');
                        return (
                          <TableRow key={String(r.id)}>
                            <TableCell className="whitespace-nowrap">{fmtDateTime(r.StartTime)}</TableCell>
                            <TableCell className="whitespace-nowrap">{fmtDateTime(r.EndTime)}</TableCell>
                            <TableCell className="whitespace-nowrap">{fmtDuration(r.DurationSeconds)}</TableCell>
                            <TableCell className="min-w-[220px]">{r.GroupName || '—'}</TableCell>
                            <TableCell className="min-w-[200px]">{status}</TableCell>
                            <TableCell className="min-w-[240px]">
                              <div className="font-medium">{obj}</div>
                              {r.ObjectAddress ? (
                                <div className="text-xs text-muted-foreground">{r.ObjectAddress}</div>
                              ) : null}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                      {!historyLoading && (history?.rows || []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} className="text-sm text-muted-foreground">
                            Нет данных. В SQLite-слепке это нормально, если дамп `ArchiveGroupResponse.sql` содержит только схему без INSERT. Для реальных данных используйте MSSQL-режим `AGENCY_DATABASE_URL=mssql+pyodbc://...`.
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </TableBody>
                  </Table>
                </div>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  );
}
