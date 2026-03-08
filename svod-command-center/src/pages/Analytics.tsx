import { MainLayout } from '@/components/layout/MainLayout';
import { useApiGet } from '@/hooks/useApiGet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DateRangePicker } from '@/components/ui/date-range-picker';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { RefreshCw, Filter, RotateCcw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import type { AnalyticsFiltersResponse, OperatorActivityRow, OperatorHandlingRow } from '@/types';
import type { DateRange } from 'react-day-picker';

type DraftFilters = {
  dateFrom: string; // YYYY-MM-DD
  dateTo: string; // YYYY-MM-DD
  operator: string;
  bucket: 'day' | 'month';
};

const defaultFilters: DraftFilters = {
  dateFrom: '',
  dateTo: '',
  operator: 'all',
  bucket: 'day',
};

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

function toStartOfDayIso(date: string): string {
  const d = new Date(`${date}T00:00:00`);
  return d.toISOString();
}

function toEndOfDayIso(date: string): string {
  const d = new Date(`${date}T23:59:59.999`);
  return d.toISOString();
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function Analytics() {
  const { data: filters, isLoading: filtersLoading, error: filtersError, refetch: refetchFilters } = useApiGet<AnalyticsFiltersResponse>(
    '/analytics/filters',
    { operators: [], actionNames: [], gbrNames: [], dateMin: null, dateMax: null }
  );

  const [draft, setDraft] = useState<DraftFilters>(defaultFilters);
  const [applied, setApplied] = useState<DraftFilters>(defaultFilters);

  // UX: if user hasn't chosen dates yet, initialize from backend min/max.
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

  const handlingPath = useMemo(() => {
    const params = new URLSearchParams();

    if (applied.dateFrom) params.set('dateFrom', toStartOfDayIso(applied.dateFrom));
    if (applied.dateTo) params.set('dateTo', toEndOfDayIso(applied.dateTo));
    if (applied.operator !== 'all') params.set('operator', applied.operator);

    const qs = params.toString();
    return `/analytics/operators/handling${qs ? `?${qs}` : ''}`;
  }, [applied]);

  const activityPath = useMemo(() => {
    const params = new URLSearchParams();

    params.set('bucket', applied.bucket);
    if (applied.dateFrom) params.set('dateFrom', toStartOfDayIso(applied.dateFrom));
    if (applied.dateTo) params.set('dateTo', toEndOfDayIso(applied.dateTo));
    if (applied.operator !== 'all') params.set('operator', applied.operator);

    const qs = params.toString();
    return `/analytics/operators/activity?${qs}`;
  }, [applied]);

  const {
    data: handling,
    isLoading: handlingLoading,
    error: handlingError,
    refetch: refetchHandling,
  } = useApiGet<OperatorHandlingRow[]>(handlingPath, [] as OperatorHandlingRow[]);

  const {
    data: activityRows,
    isLoading: activityLoading,
    error: activityError,
    refetch: refetchActivity,
  } = useApiGet<OperatorActivityRow[]>(activityPath, [] as OperatorActivityRow[]);

  const activitySeries = useMemo(() => {
    // If operator selected, backend already returns single operator rows.
    // If not selected, aggregate all operators per bucket.
    const byBucket = new Map<string, number>();
    for (const r of activityRows || []) {
      byBucket.set(r.bucket, (byBucket.get(r.bucket) || 0) + (r.actions || 0));
    }
    return Array.from(byBucket.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([bucket, actions]) => ({ bucket, actions }));
  }, [activityRows]);

  const applyFilters = () => {
    setApplied(draft);
  };

  const resetFilters = () => {
    setDraft(defaultFilters);
    setApplied(defaultFilters);
  };

  return (
    <MainLayout title="Аналитика" subtitle="Скорость обработки и активность операторов">
      <div className="space-y-4 animate-fade-in">
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            {filtersLoading ? 'Загрузка фильтров…' : filters?.dateMin ? `Данные: ${filters.dateMin.slice(0, 10)} → ${filters.dateMax?.slice(0, 10)}` : 'Данные не найдены'}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2" onClick={() => { refetchFilters(); refetchHandling(); refetchActivity(); }}>
              <RefreshCw className="h-4 w-4" />
              Обновить
            </Button>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
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

            <Select value={draft.operator} onValueChange={(v) => setDraft((s) => ({ ...s, operator: v }))}>
              <SelectTrigger className="w-[240px] bg-background">
                <SelectValue placeholder="Оператор" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все операторы</SelectItem>
                {(filters?.operators || []).map((o) => (
                  <SelectItem key={o} value={o}>
                    {o}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={draft.bucket} onValueChange={(v) => setDraft((s) => ({ ...s, bucket: v as any }))}>
              <SelectTrigger className="w-[160px] bg-background">
                <SelectValue placeholder="Группировка" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="day">По дням</SelectItem>
                <SelectItem value="month">По месяцам</SelectItem>
              </SelectContent>
            </Select>

            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" className="gap-2" onClick={applyFilters}>
                <Filter className="h-4 w-4" />
                Применить
              </Button>
              <Button variant="ghost" size="sm" className="gap-2" onClick={resetFilters}>
                <RotateCcw className="h-4 w-4" />
                Сбросить
              </Button>
            </div>
          </div>
          {filtersError && <div className="mt-2 text-sm text-destructive">Ошибка фильтров: {filtersError}</div>}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <Card className="xl:col-span-2 p-6">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-foreground">Активность</h3>
              <p className="text-sm text-muted-foreground">Количество действий по периоду</p>
            </div>

            {activityError && <div className="text-sm text-destructive">Ошибка: {activityError}</div>}
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={activitySeries} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorActions" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="bucket" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--popover))',
                      borderColor: 'hsl(var(--border))',
                      borderRadius: '8px',
                      color: 'hsl(var(--foreground))',
                    }}
                    labelStyle={{ color: 'hsl(var(--muted-foreground))' }}
                  />
                  <Area type="monotone" dataKey="actions" name="Действия" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#colorActions)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-3 flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-2" onClick={refetchActivity}>
                <RefreshCw className="h-4 w-4" />
                Обновить график
              </Button>
              {activityLoading && <span className="text-sm text-muted-foreground">Загрузка…</span>}
            </div>
          </Card>

          <Card className="p-6">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-foreground">Скорость обработки</h3>
              <p className="text-sm text-muted-foreground">Средняя длительность: прием → окончание</p>
            </div>

            {handlingError && <div className="text-sm text-destructive">Ошибка: {handlingError}</div>}

            <div className="max-h-[340px] overflow-auto rounded-md border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-muted-foreground">
                  <tr>
                    <th className="text-left font-medium px-3 py-2">Оператор</th>
                    <th className="text-right font-medium px-3 py-2">Событий</th>
                    <th className="text-right font-medium px-3 py-2">Среднее</th>
                  </tr>
                </thead>
                <tbody>
                  {(handling || []).slice(0, 50).map((r) => (
                    <tr key={r.operator} className="border-t border-border">
                      <td className="px-3 py-2 text-foreground">{r.operator}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{r.events}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatDuration(r.avgSeconds)}</td>
                    </tr>
                  ))}
                  {!handlingLoading && (handling || []).length === 0 && (
                    <tr>
                      <td className="px-3 py-6 text-muted-foreground" colSpan={3}>
                        Нет данных по выбранным фильтрам
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="mt-3 flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-2" onClick={refetchHandling}>
                <RefreshCw className="h-4 w-4" />
                Обновить таблицу
              </Button>
              {handlingLoading && <span className="text-sm text-muted-foreground">Загрузка…</span>}
            </div>
          </Card>
        </div>

        {(() => {
          const combined = [filtersError, handlingError, activityError].filter(Boolean).join(' | ');
          if (!combined) return null;

          const isForbidden = combined.toLowerCase().includes('missing permissions') || combined.toLowerCase().includes('forbidden');
          return (
            <div className={isForbidden ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'}>
              {isForbidden
                ? 'Нет доступа к аналитике: требуется право analytics:read (роль admin/analyst).'
                : 'Есть ошибки загрузки. Проверьте доступность бэкенда и токен.'}
            </div>
          );
        })()}
      </div>
    </MainLayout>
  );
}
