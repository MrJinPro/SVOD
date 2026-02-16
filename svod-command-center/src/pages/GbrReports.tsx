import { MainLayout } from '@/components/layout/MainLayout';
import { useApiGet } from '@/hooks/useApiGet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { apiFetchRaw } from '@/lib/api';
import { Download, RefreshCw, RotateCcw, Filter } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { AnalyticsFiltersResponse, GbrTripsResponse } from '@/types';

type Draft = {
  dateFrom: string;
  dateTo: string;
  gbrName: string;
  objectId: string;
};

const defaultDraft: Draft = {
  dateFrom: '',
  dateTo: '',
  gbrName: 'all',
  objectId: '',
};

function toStartOfDayIso(date: string): string {
  return new Date(`${date}T00:00:00`).toISOString();
}

function toEndOfDayIso(date: string): string {
  return new Date(`${date}T23:59:59.999`).toISOString();
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

async function downloadCsv(path: string, filename: string) {
  const res = await apiFetchRaw(path, { method: 'GET' });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function GbrReports() {
  const { data: filters, error: filtersError } = useApiGet<AnalyticsFiltersResponse>(
    '/analytics/filters',
    { operators: [], actionNames: [], gbrNames: [], dateMin: null, dateMax: null }
  );

  const [draft, setDraft] = useState<Draft>(defaultDraft);
  const [applied, setApplied] = useState<Draft>(defaultDraft);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!filters?.dateMin || !filters?.dateMax) return;
    const minDay = String(filters.dateMin).slice(0, 10);
    const maxDay = String(filters.dateMax).slice(0, 10);

    setDraft((v) => {
      if (v.dateFrom || v.dateTo) return v;
      return { ...v, dateFrom: minDay, dateTo: maxDay };
    });
    setApplied((v) => {
      if (v.dateFrom || v.dateTo) return v;
      return { ...v, dateFrom: minDay, dateTo: maxDay };
    });
  }, [filters?.dateMin, filters?.dateMax]);

  const listPath = useMemo(() => {
    const params = new URLSearchParams();

    if (applied.dateFrom) params.set('dateFrom', toStartOfDayIso(applied.dateFrom));
    if (applied.dateTo) params.set('dateTo', toEndOfDayIso(applied.dateTo));
    if (applied.gbrName !== 'all') params.set('gbrName', applied.gbrName);
    if (applied.objectId.trim()) params.set('objectId', applied.objectId.trim());

    const limit = 200;
    const offset = (page - 1) * limit;
    params.set('limit', String(limit));
    params.set('offset', String(offset));

    return `/analytics/gbr/trips?${params.toString()}`;
  }, [applied, page]);

  const { data: trips, isLoading, error, refetch } = useApiGet<GbrTripsResponse>(listPath, {
    data: [],
    total: 0,
    limit: 200,
    offset: 0,
  });

  const totalPages = Math.max(1, Math.ceil((trips.total || 0) / (trips.limit || 200)));

  const exportPath = useMemo(() => {
    const params = new URLSearchParams();

    if (applied.dateFrom) params.set('dateFrom', toStartOfDayIso(applied.dateFrom));
    if (applied.dateTo) params.set('dateTo', toEndOfDayIso(applied.dateTo));
    if (applied.gbrName !== 'all') params.set('gbrName', applied.gbrName);
    if (applied.objectId.trim()) params.set('objectId', applied.objectId.trim());

    return `/analytics/gbr/trips/export?${params.toString()}`;
  }, [applied]);

  const forbiddenHint = useMemo(() => {
    const combined = [filtersError, error].filter(Boolean).join(' | ').toLowerCase();
    if (!combined) return null;
    if (combined.includes('missing permissions') || combined.includes('forbidden')) {
      return 'Нет доступа: требуется право analytics:read (роль admin/analyst).';
    }
    return null;
  }, [filtersError, error]);

  return (
    <MainLayout title="Отчёт ГБР" subtitle="Куда и когда выезжали группы реагирования">
      <div className="space-y-4 animate-fade-in">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Период:</span>
              <Input
                type="date"
                className="w-[160px] bg-background"
                value={draft.dateFrom}
                onChange={(e) => setDraft((v) => ({ ...v, dateFrom: e.target.value }))}
              />
              <span className="text-sm text-muted-foreground">—</span>
              <Input
                type="date"
                className="w-[160px] bg-background"
                value={draft.dateTo}
                onChange={(e) => setDraft((v) => ({ ...v, dateTo: e.target.value }))}
              />
            </div>

            <Select value={draft.gbrName} onValueChange={(v) => setDraft((s) => ({ ...s, gbrName: v }))}>
              <SelectTrigger className="w-[260px] bg-background">
                <SelectValue placeholder="ГБР" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все ГБР</SelectItem>
                {(filters?.gbrNames || []).map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Input
              className="w-[240px] bg-background"
              placeholder="ObjectId (Panel_id)"
              value={draft.objectId}
              onChange={(e) => setDraft((v) => ({ ...v, objectId: e.target.value }))}
            />

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                className="gap-2"
                onClick={() => {
                  setApplied(draft);
                  setPage(1);
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
                  setDraft(defaultDraft);
                  setApplied(defaultDraft);
                  setPage(1);
                }}
              >
                <RotateCcw className="h-4 w-4" />
                Сбросить
              </Button>
              <Button variant="outline" size="sm" className="gap-2" onClick={refetch}>
                <RefreshCw className="h-4 w-4" />
                Обновить
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => downloadCsv(exportPath, `gbr-trips-${new Date().toISOString().slice(0, 10)}.csv`)}
              >
                <Download className="h-4 w-4" />
                CSV
              </Button>
            </div>
          </div>

          {forbiddenHint && <div className="mt-2 text-sm text-destructive">{forbiddenHint}</div>}
          {filtersError && !forbiddenHint && <div className="mt-2 text-sm text-destructive">Ошибка фильтров: {filtersError}</div>}
        </div>

        <Card className="p-0 overflow-hidden">
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th className="text-left font-medium px-3 py-2">Вызов</th>
                  <th className="text-left font-medium px-3 py-2">Прибытие</th>
                  <th className="text-left font-medium px-3 py-2">ГБР</th>
                  <th className="text-left font-medium px-3 py-2">Объект</th>
                  <th className="text-right font-medium px-3 py-2">В пути</th>
                </tr>
              </thead>
              <tbody>
                {(trips.data || []).map((r) => (
                  <tr key={`${r.eventId}:${r.gbrName}:${r.calledAt}`} className="border-t border-border">
                    <td className="px-3 py-2 tabular-nums">{r.calledAt ? r.calledAt.replace('T', ' ').slice(0, 19) : '—'}</td>
                    <td className="px-3 py-2 tabular-nums">{r.arrivedAt ? r.arrivedAt.replace('T', ' ').slice(0, 19) : (r.cancelledAt ? 'Отмена' : '—')}</td>
                    <td className="px-3 py-2">{r.gbrName}</td>
                    <td className="px-3 py-2">
                      <div className="text-foreground">{r.objectName || r.objectId || '—'}</div>
                      <div className="text-xs text-muted-foreground">
                        {[r.responsibleName || r.clientName || null, r.objectId ? `№ ${r.objectId}` : null]
                          .filter(Boolean)
                          .join(' • ')}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatDuration(r.travelSeconds)}</td>
                  </tr>
                ))}
                {!isLoading && (trips.data || []).length === 0 && (
                  <tr>
                    <td className="px-3 py-6 text-muted-foreground" colSpan={5}>
                      Нет данных по выбранным фильтрам
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {error && !forbiddenHint && <div className="text-sm text-destructive">Ошибка загрузки: {error}</div>}

        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{isLoading ? 'Загрузка…' : `Показано ${trips.data.length} из ${trips.total}`}</span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
              Назад
            </Button>
            <span className="tabular-nums">{page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
              Вперёд
            </Button>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
