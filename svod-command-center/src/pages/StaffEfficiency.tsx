import { MainLayout } from '@/components/layout/MainLayout';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useApiGet } from '@/hooks/useApiGet';
import type { OperatorLiveRow } from '@/types';
import { Printer, RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

type Draft = {
  windowMinutes: string;
  onlineMinutes: string;
};

const defaultDraft: Draft = {
  windowMinutes: '60',
  onlineMinutes: '10',
};

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatSince(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return '—';
  if (seconds < 60) return `${seconds}с`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}м ${s}с`;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${h}ч ${mm}м`;
}

function deriveStatus(row: OperatorLiveRow): string {
  if (!row.lastActionAt) return 'Нет данных';
  if (!row.online) return 'Не в сети';
  const seconds = row.secondsSinceLastAction ?? null;
  if (seconds !== null && seconds <= 60) return 'Активен';
  return 'В сети';
}

export default function StaffEfficiency() {
  const [draft, setDraft] = useState<Draft>(defaultDraft);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const path = useMemo(() => {
    const params = new URLSearchParams();
    params.set('windowMinutes', draft.windowMinutes);
    params.set('onlineMinutes', draft.onlineMinutes);
    return `/analytics/operators/live?${params.toString()}`;
  }, [draft.windowMinutes, draft.onlineMinutes]);

  const { data, isLoading, error, refetch } = useApiGet<OperatorLiveRow[]>(path, [] as OperatorLiveRow[]);

  useEffect(() => {
    if (!autoRefresh) return;
    const t = window.setInterval(() => {
      refetch();
    }, 10_000);
    return () => window.clearInterval(t);
  }, [autoRefresh, refetch]);

  const generatedAt = useMemo(() => new Date().toLocaleString('ru-RU'), [data?.length, isLoading]);

  return (
    <MainLayout
      title="Эффективность сотрудников"
      subtitle="Онлайн/нагрузка/скорость обработки по действиям операторов"
    >
      <div className="space-y-4 animate-fade-in">
        <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
          <div className="text-sm text-muted-foreground">Сформировано: {generatedAt}</div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2" onClick={refetch}>
              <RefreshCw className="h-4 w-4" />
              Обновить
            </Button>
            <Button
              variant="secondary"
              size="sm"
              className="gap-2"
              onClick={() => window.print()}
            >
              <Printer className="h-4 w-4" />
              Печать
            </Button>
          </div>
        </div>

        <Card className="p-4 print:hidden">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Окно анализа:</span>
              <Select
                value={draft.windowMinutes}
                onValueChange={(v) => setDraft((s) => ({ ...s, windowMinutes: v }))}
              >
                <SelectTrigger className="w-[180px] bg-background">
                  <SelectValue placeholder="Окно" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">15 минут</SelectItem>
                  <SelectItem value="60">60 минут</SelectItem>
                  <SelectItem value="180">3 часа</SelectItem>
                  <SelectItem value="720">12 часов</SelectItem>
                  <SelectItem value="1440">24 часа</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Онлайн, если было действие за:</span>
              <Select
                value={draft.onlineMinutes}
                onValueChange={(v) => setDraft((s) => ({ ...s, onlineMinutes: v }))}
              >
                <SelectTrigger className="w-[180px] bg-background">
                  <SelectValue placeholder="Онлайн" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">5 минут</SelectItem>
                  <SelectItem value="10">10 минут</SelectItem>
                  <SelectItem value="20">20 минут</SelectItem>
                  <SelectItem value="30">30 минут</SelectItem>
                  <SelectItem value="60">60 минут</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} />
              <Label className="text-sm">Автообновление (10с)</Label>
            </div>
          </div>

          {error && <div className="mt-2 text-sm text-destructive">Ошибка: {error}</div>}
        </Card>

        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Операторы</h3>
              <p className="text-sm text-muted-foreground">
                Показатели строятся по таблице действий (eventservice → event_actions)
              </p>
            </div>
            <div className="text-sm text-muted-foreground">
              {isLoading ? 'Загрузка…' : `Строк: ${(data || []).length}`}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 text-left font-medium">Сотрудник</th>
                  <th className="py-2 text-left font-medium">Статус</th>
                  <th className="py-2 text-left font-medium">Последнее действие</th>
                  <th className="py-2 text-left font-medium">Когда</th>
                  <th className="py-2 text-left font-medium">Компьютер</th>
                  <th className="py-2 text-right font-medium">Действия 5м</th>
                  <th className="py-2 text-right font-medium">Действия 15м</th>
                  <th className="py-2 text-right font-medium">Действия (окно)</th>
                  <th className="py-2 text-right font-medium">События (окно)</th>
                  <th className="py-2 text-right font-medium">Средн. обработка</th>
                  <th className="py-2 text-right font-medium">Обработано</th>
                </tr>
              </thead>
              <tbody>
                {(data || []).map((r) => {
                  const status = deriveStatus(r);
                  return (
                    <tr key={r.operator} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-2 pr-3 font-medium text-foreground whitespace-nowrap">
                        {r.operator}
                      </td>
                      <td className="py-2 pr-3 whitespace-nowrap">
                        <span
                          className={
                            r.online
                              ? 'rounded-full bg-emerald-500/15 px-2 py-1 text-emerald-600'
                              : 'rounded-full bg-muted px-2 py-1 text-muted-foreground'
                          }
                        >
                          {status}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-foreground/90 min-w-[260px]">{r.lastActionName || '—'}</td>
                      <td className="py-2 pr-3 text-muted-foreground whitespace-nowrap">
                        {r.lastActionAt ? `${formatSince(r.secondsSinceLastAction)} назад` : '—'}
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground whitespace-nowrap">{r.computer || '—'}</td>
                      <td className="py-2 text-right tabular-nums">{r.actions5m ?? 0}</td>
                      <td className="py-2 text-right tabular-nums">{r.actions15m ?? 0}</td>
                      <td className="py-2 text-right tabular-nums">{r.actionsWindow ?? 0}</td>
                      <td className="py-2 text-right tabular-nums">{r.eventsWindow ?? 0}</td>
                      <td className="py-2 text-right tabular-nums">{formatDuration(r.avgHandlingSeconds)}</td>
                      <td className="py-2 text-right tabular-nums">{r.handledEvents ?? 0}</td>
                    </tr>
                  );
                })}

                {!isLoading && (data || []).length === 0 && (
                  <tr>
                    <td colSpan={11} className="py-6 text-center text-sm text-muted-foreground">
                      Данных по операторам нет
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-3 text-xs text-muted-foreground">
            Онлайн определяется по последнему действию за последние {draft.onlineMinutes} минут.
          </div>
        </Card>

        {/* Print-only header */}
        <div className="hidden print:block">
          <div className="text-lg font-semibold">Эффективность сотрудников</div>
          <div className="text-sm text-muted-foreground">Сформировано: {generatedAt}</div>
          <div className="text-sm text-muted-foreground">
            Окно анализа: {draft.windowMinutes} мин, онлайн порог: {draft.onlineMinutes} мин
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
