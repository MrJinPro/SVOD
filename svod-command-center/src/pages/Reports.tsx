import { MainLayout } from '@/components/layout/MainLayout';
import { ReportsTable } from '@/components/reports/ReportsTable';
import { useApiGet } from '@/hooks/useApiGet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DateRangePicker } from '@/components/ui/date-range-picker';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Check, ChevronsUpDown, Plus, RefreshCw } from 'lucide-react';
import { API_BASE_URL, apiFetchRaw, apiGet, apiPost } from '@/lib/api';
import { loadUiSettings } from '@/lib/uiSettings';
import { appendCommonEventFilterParams, appendEventDateRangeParams } from '@/lib/eventFilters';
import { toast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReportStatus, ReportType } from '@/types';
import type { DateRange } from 'react-day-picker';
import type { AnalyticsFiltersResponse, GbrTripRow, GbrTripsResponse } from '@/types';
import { ScrollArea } from '@/components/ui/scroll-area';

type CreateReportKind = 'objectsByCode' | 'gbrRaportXlsx' | 'eventsRaportXlsx' | 'alarmMessages' | 'pcnLedger';

function formatLocalYYYYMMDD(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

type EventCodeItem = {
  code: string;
  codeText?: string | null;
  count?: number;
};

function EventCodeCombobox({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<EventCodeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;

    const getViewport = () => {
      const root = scrollAreaRef.current;
      if (!root) return null;
      return root.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement | null;
    };

    const onWheelCapture = (e: WheelEvent) => {
      const root = scrollAreaRef.current;
      if (!root) return;
      const target = e.target as Node | null;
      if (!target || !root.contains(target)) return;

      const viewport = getViewport();
      if (!viewport) return;
      if (viewport.scrollHeight <= viewport.clientHeight) return;

      let delta = e.deltaY;
      if (e.deltaMode === 1) delta *= 16; // lines -> px (approx)
      else if (e.deltaMode === 2) delta *= viewport.clientHeight; // pages -> px

      viewport.scrollTop += delta;
      e.preventDefault();
      e.stopPropagation();
    };

    document.addEventListener('wheel', onWheelCapture, { capture: true, passive: false });
    return () => {
      document.removeEventListener('wheel', onWheelCapture as any, { capture: true } as any);
    };
  }, [open]);

  useEffect(() => {
    let cancelled = false;
    const q = query.trim();
    const t = window.setTimeout(async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (q) params.set('query', q);
        params.set('limit', '100');
        const res = await apiGet<EventCodeItem[]>(`/reports/event-codes?${params.toString()}`);
        if (!cancelled) setItems(res || []);
      } catch (e: any) {
        if (!cancelled) {
          setItems([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [query]);

  const selected = useMemo(() => items.find((i) => i.code === value), [items, value]);
  const buttonLabel = value
    ? `${value}${selected?.codeText ? ` — ${selected.codeText}` : ''}`
    : 'Выберите код события…';

  const canUseTyped = useMemo(() => {
    const q = query.trim();
    if (!q) return false;
    if (q.length > 16) return false;
    // Allow typical formats: E1001, 1001, A12, etc.
    return /^[A-Za-z0-9._-]+$/.test(q);
  }, [query]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full sm:w-[520px] justify-between"
        >
          <span className="truncate text-left">{buttonLabel}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[520px] max-w-[calc(100vw-2rem)] p-0" align="start">
        <Command>
          <CommandInput
            placeholder="Поиск по коду или расшифровке…"
            value={query}
            onValueChange={setQuery}
          />
          <ScrollArea
            ref={scrollAreaRef}
            className="h-[300px]"
          >
            <CommandList className="max-h-none overflow-visible">
              <CommandEmpty>{loading ? 'Загрузка…' : 'Ничего не найдено'}</CommandEmpty>
              <CommandGroup>
                {canUseTyped ? (
                  <CommandItem
                    key={`typed:${query.trim()}`}
                    value={query.trim()}
                    onSelect={() => {
                      onChange(query.trim());
                      setOpen(false);
                    }}
                  >
                    <Check className={cn('mr-2 h-4 w-4', value === query.trim() ? 'opacity-100' : 'opacity-0')} />
                    <div className="min-w-0">
                      <div className="text-sm text-foreground">Использовать код: <span className="font-mono">{query.trim()}</span></div>
                      <div className="text-xs text-muted-foreground">Ввод вручную (если нет в справочнике)</div>
                    </div>
                  </CommandItem>
                ) : null}
                {(items || []).map((it) => (
                  <CommandItem
                    key={it.code}
                    value={`${it.code} ${it.codeText || ''}`}
                    onSelect={() => {
                      onChange(it.code);
                      setOpen(false);
                    }}
                  >
                    <Check
                      className={cn('mr-2 h-4 w-4', value === it.code ? 'opacity-100' : 'opacity-0')}
                    />
                    <div className="flex w-full items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-mono text-sm text-foreground">{it.code}</div>
                        {it.codeText ? (
                          <div className="truncate text-xs text-muted-foreground">{it.codeText}</div>
                        ) : null}
                      </div>
                      {typeof it.count === 'number' ? (
                        <div className="text-xs text-muted-foreground">{it.count.toLocaleString('ru-RU')}</div>
                      ) : null}
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </ScrollArea>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export default function Reports() {
  const { data: reports, refetch } = useApiGet('/reports', []);

  const { data: analyticsFilters } = useApiGet<AnalyticsFiltersResponse>('/analytics/filters', {
    operators: [],
    actionNames: [],
    gbrNames: [],
    dateMin: null,
    dateMax: null,
  });

  const [typeFilter, setTypeFilter] = useState<'all' | ReportType>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | ReportStatus>('all');

  const [createOpen, setCreateOpen] = useState(false);
  const [createKind, setCreateKind] = useState<CreateReportKind>('objectsByCode');

  const [pcnOperatorQuery, setPcnOperatorQuery] = useState('');
  const [pcnHideOperatorNames, setPcnHideOperatorNames] = useState(false);
  const [pcnPay0, setPcnPay0] = useState('0');
  const [pcnPay1, setPcnPay1] = useState('330');
  const [pcnPay2, setPcnPay2] = useState('430');
  const [pcnPay3, setPcnPay3] = useState('480');

  const [pcnThr3_1, setPcnThr3_1] = useState('29');
  const [pcnThr3_2, setPcnThr3_2] = useState('36');
  const [pcnThr3_3, setPcnThr3_3] = useState('40');

  const [pcnThr4_1, setPcnThr4_1] = useState('21');
  const [pcnThr4_2, setPcnThr4_2] = useState('27');
  const [pcnThr4_3, setPcnThr4_3] = useState('30');

  const [pcnThr5_1, setPcnThr5_1] = useState('17');
  const [pcnThr5_2, setPcnThr5_2] = useState('23');
  const [pcnThr5_3, setPcnThr5_3] = useState('26');

  const [dateRange, setDateRange] = useState<DateRange | undefined>(() => {
    const now = new Date();
    const from = new Date(now);
    from.setDate(from.getDate() - 7);
    return { from, to: now };
  });

  const [timeFrom, setTimeFrom] = useState('00:00');
  const [timeTo, setTimeTo] = useState('23:59');
  const [clientName, setClientName] = useState('');
  const [objectQuery, setObjectQuery] = useState('');
  const [eventCode, setEventCode] = useState('');

  const [eventsSearch, setEventsSearch] = useState('');
  const [eventsObjectId, setEventsObjectId] = useState('');
  const [eventsType, setEventsType] = useState<'all' | string>('all');
  const [eventsSeverity, setEventsSeverity] = useState<'all' | string>('all');
  const [eventsStatus, setEventsStatus] = useState<'all' | string>('all');
  const [eventsOnlyWithOperatorComment, setEventsOnlyWithOperatorComment] = useState(false);
  const [eventsIncludeSystem, setEventsIncludeSystem] = useState(false);
  const [eventsIncludeCancelled, setEventsIncludeCancelled] = useState(false);

  const [gbrName, setGbrName] = useState<'all' | string>('all');
  const [gbrObjectId, setGbrObjectId] = useState('');
  const [gbrPreview, setGbrPreview] = useState<GbrTripRow[]>([]);
  const [gbrPreviewLoading, setGbrPreviewLoading] = useState(false);

  const setRangeToYear = (year: number) => {
    setDateRange({ from: new Date(year, 0, 1), to: new Date(year, 11, 31) });
  };

  const setRangeToMonth = (year: number, month1to12: number) => {
    setDateRange({ from: new Date(year, month1to12 - 1, 1), to: new Date(year, month1to12, 0) });
  };

  const applyQuickRange = (kind: 'y2024' | 'y2025' | 'curMonth' | 'prevMonth') => {
    const now = new Date();
    if (kind === 'y2024') return setRangeToYear(2024);
    if (kind === 'y2025') return setRangeToYear(2025);
    if (kind === 'curMonth') return setRangeToMonth(now.getFullYear(), now.getMonth() + 1);
    const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    return setRangeToMonth(prev.getFullYear(), prev.getMonth() + 1);
  };

  const QuickRangeButtons = () => (
    <div className="flex flex-wrap items-center gap-2">
      <Button type="button" variant="outline" size="sm" onClick={() => applyQuickRange('y2024')}>
        2024
      </Button>
      <Button type="button" variant="outline" size="sm" onClick={() => applyQuickRange('y2025')}>
        2025
      </Button>
      <Button type="button" variant="outline" size="sm" onClick={() => applyQuickRange('curMonth')}>
        Текущий месяц
      </Button>
      <Button type="button" variant="outline" size="sm" onClick={() => applyQuickRange('prevMonth')}>
        Прошлый месяц
      </Button>
    </div>
  );

  const downloadBlob = async (path: string, filename: string) => {
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
  };

  const loadGbrPreview = async () => {
    if (!dateRange?.from || !dateRange?.to) {
      toast({ title: 'Отчёт', description: 'Выберите период (от и до).', variant: 'destructive' });
      return;
    }
    setGbrPreviewLoading(true);
    try {
      const params = new URLSearchParams();
      // Use UTC ISO like other pages (Analytics/GbrReports)
      appendEventDateRangeParams(params, { dateRange, timeFrom, timeTo });
      if (gbrName !== 'all') params.set('gbrName', String(gbrName));
      if (gbrObjectId.trim()) params.set('objectId', gbrObjectId.trim());
      params.set('limit', '2000');
      params.set('offset', '0');
      const res = await apiGet<GbrTripsResponse>(`/analytics/gbr/trips?${params.toString()}`);
      setGbrPreview(res?.data || []);
    } catch (e: any) {
      toast({
        title: 'Отчёт',
        description: e?.message || 'Ошибка загрузки предпросмотра',
        variant: 'destructive',
      });
      setGbrPreview([]);
    } finally {
      setGbrPreviewLoading(false);
    }
  };

  const downloadGbrRaportXlsx = async () => {
    if (!dateRange?.from || !dateRange?.to) {
      toast({ title: 'Отчёт', description: 'Выберите период (от и до).', variant: 'destructive' });
      return;
    }
    const params = new URLSearchParams();
    appendEventDateRangeParams(params, { dateRange, timeFrom, timeTo });
    if (gbrName !== 'all') params.set('gbrName', String(gbrName));
    if (gbrObjectId.trim()) params.set('objectId', gbrObjectId.trim());
    const name = `raport-gbr-${formatLocalYYYYMMDD(new Date())}.xlsx`;
    await downloadBlob(`/analytics/gbr/trips/export/xlsx?${params.toString()}`, name);
  };

  const createReportInHistory = async () => {
    try {
      if (createKind === 'objectsByCode') {
        if (!eventCode.trim()) {
          toast({ title: 'Отчёт', description: 'Выберите код события.', variant: 'destructive' });
          return;
        }
        if (!dateRange?.from || !dateRange?.to) {
          toast({ title: 'Отчёт', description: 'Выберите период (от и до).', variant: 'destructive' });
          return;
        }
        const params = new URLSearchParams();
        params.set('eventCode', eventCode.trim());
        appendEventDateRangeParams(params, { dateRange, timeFrom, timeTo });
        if (clientName.trim()) params.set('clientName', clientName.trim());
        if (objectQuery.trim()) params.set('objectQuery', objectQuery.trim());
        await apiPost(`/reports/generate/objects-by-code?${params.toString()}`);
      } else if (createKind === 'gbrRaportXlsx') {
        if (!dateRange?.from || !dateRange?.to) {
          toast({ title: 'Отчёт', description: 'Выберите период (от и до).', variant: 'destructive' });
          return;
        }
        const params = new URLSearchParams();
        appendEventDateRangeParams(params, { dateRange, timeFrom, timeTo });
        if (gbrName !== 'all') params.set('gbrName', String(gbrName));
        if (gbrObjectId.trim()) params.set('objectId', gbrObjectId.trim());
        await apiPost(`/reports/generate/gbr-raport-xlsx?${params.toString()}`);
      } else if (createKind === 'eventsRaportXlsx' || createKind === 'alarmMessages') {
        if (!dateRange?.from || !dateRange?.to) {
          toast({ title: 'Отчёт', description: 'Выберите период (от и до).', variant: 'destructive' });
          return;
        }
        const params = new URLSearchParams();
        appendEventDateRangeParams(params, { dateRange, timeFrom, timeTo });
        appendCommonEventFilterParams(params, {
          search: eventsSearch,
          objectId: eventsObjectId,
          type: String(eventsType),
          severity: String(eventsSeverity),
          status: String(eventsStatus),
          onlyWithOperatorComment: eventsOnlyWithOperatorComment,
          includeSystem: eventsIncludeSystem,
          includeCancelled: eventsIncludeCancelled,
        });

        const path = createKind === 'alarmMessages'
          ? `/reports/generate/alarm-messages-xlsx?${params.toString()}`
          : `/reports/generate/events-raport-xlsx?${params.toString()}`;

        await apiPost(path);
      } else if (createKind === 'pcnLedger') {
        if (!dateRange?.from || !dateRange?.to) {
          toast({ title: 'Отчёт', description: 'Выберите период (от и до).', variant: 'destructive' });
          return;
        }
        const params = new URLSearchParams();
        appendEventDateRangeParams(params, { dateRange, timeFrom, timeTo });
        if (pcnOperatorQuery.trim()) params.set('operatorQuery', pcnOperatorQuery.trim());
        if (pcnHideOperatorNames) params.set('hideOperatorNames', 'true');

        // Shifts: configurable boundaries (Settings -> localStorage)
        const ui = loadUiSettings();
        if (ui.shiftDayStart) params.set('dayStart', ui.shiftDayStart);
        if (ui.shiftNightStart) params.set('nightStart', ui.shiftNightStart);

        // Configurable payouts/thresholds (will be printed in XLSX header)
        if (pcnPay0.trim()) params.set('pay0', pcnPay0.trim());
        if (pcnPay1.trim()) params.set('pay1', pcnPay1.trim());
        if (pcnPay2.trim()) params.set('pay2', pcnPay2.trim());
        if (pcnPay3.trim()) params.set('pay3', pcnPay3.trim());

        if (pcnThr3_1.trim()) params.set('thr3_1', pcnThr3_1.trim());
        if (pcnThr3_2.trim()) params.set('thr3_2', pcnThr3_2.trim());
        if (pcnThr3_3.trim()) params.set('thr3_3', pcnThr3_3.trim());

        if (pcnThr4_1.trim()) params.set('thr4_1', pcnThr4_1.trim());
        if (pcnThr4_2.trim()) params.set('thr4_2', pcnThr4_2.trim());
        if (pcnThr4_3.trim()) params.set('thr4_3', pcnThr4_3.trim());

        if (pcnThr5_1.trim()) params.set('thr5_1', pcnThr5_1.trim());
        if (pcnThr5_2.trim()) params.set('thr5_2', pcnThr5_2.trim());
        if (pcnThr5_3.trim()) params.set('thr5_3', pcnThr5_3.trim());

        await apiPost(`/reports/generate/pcn-ledger-xlsx?${params.toString()}`);
      }

      toast({ title: 'Отчёт', description: 'Отчёт добавлен в историю.' });
      setCreateOpen(false);
      await refetch();
    } catch (e: any) {
      toast({
        title: 'Отчёт',
        description: e?.message || 'Ошибка формирования отчёта',
        variant: 'destructive',
      });
    }
  };

  const filteredReports = useMemo(() => {
    return (reports || []).filter((r: any) => {
      // Defensive: hide legacy daily reports even if backend still returns them
      if (r?.type === 'daily') return false;
      if (typeFilter !== 'all' && r.type !== typeFilter) return false;
      if (statusFilter !== 'all' && r.status !== statusFilter) return false;
      return true;
    });
  }, [reports, statusFilter, typeFilter]);

  return (
    <MainLayout 
      title="Отчёты" 
      subtitle="Сформированные и запланированные отчёты"
    >
      <div className="space-y-4 animate-fade-in">
        {/* Actions bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as any)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Тип отчёта" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все типы</SelectItem>
                <SelectItem value="objectsByCode">Объекты по коду</SelectItem>
                <SelectItem value="gbrRaportXlsx">Рапорт (ГБР)</SelectItem>
                <SelectItem value="eventsRaportXlsx">Рапорт по событиям</SelectItem>
                <SelectItem value="alarmMessages">Тревожные сообщения</SelectItem>
                <SelectItem value="pcnLedger">Ведомость (ПЦН)</SelectItem>
                <SelectItem value="weekly">Недельные</SelectItem>
                <SelectItem value="monthly">Месячные</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as any)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Статус" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все статусы</SelectItem>
                <SelectItem value="generated">Сформирован</SelectItem>
                <SelectItem value="sent">Отправлен</SelectItem>
                <SelectItem value="pending">Ожидает</SelectItem>
                <SelectItem value="failed">Ошибка</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2" onClick={refetch}>
              <RefreshCw className="h-4 w-4" />
              Обновить
            </Button>
            <Button
              size="sm"
              className="gap-2"
              onClick={() => {
                setCreateOpen(true);
              }}
            >
              <Plus className="h-4 w-4" />
              Создать отчёт
            </Button>
          </div>
        </div>

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent fullscreenable className="sm:max-w-[760px] max-w-[calc(100vw-2rem)] overflow-hidden">
            <DialogHeader>
              <DialogTitle>Создать отчёт</DialogTitle>
              <DialogDescription>
                Выберите тип отчёта и параметры.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <Select value={createKind} onValueChange={(v) => setCreateKind(v as CreateReportKind)}>
                  <SelectTrigger className="w-full sm:w-[360px]">
                    <SelectValue placeholder="Тип отчёта" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="objectsByCode">Объекты по коду события (XLSX)</SelectItem>
                    <SelectItem value="gbrRaportXlsx">Рапорт (ГБР) по шаблону (XLSX)</SelectItem>
                    <SelectItem value="eventsRaportXlsx">Рапорт по событиям (XLSX)</SelectItem>
                    <SelectItem value="alarmMessages">Тревожные сообщения (XLSX)</SelectItem>
                    <SelectItem value="pcnLedger">Ведомость по тревогам (ПЦН) (XLSX)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {createKind === 'objectsByCode' ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Период</div>
                      <QuickRangeButtons />
                      <div className="flex flex-wrap items-end gap-2">
                        <DateRangePicker
                          value={dateRange}
                          onChange={setDateRange}
                          placeholder="Выберите период"
                          triggerClassName="w-full sm:w-[280px]"
                          numberOfMonths={2}
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Время (от/до)</div>
                      <div className="flex items-center gap-2">
                        <Input type="time" className="w-[140px] bg-background" value={timeFrom} onChange={(e) => setTimeFrom(e.target.value)} />
                        <div className="text-muted-foreground">—</div>
                        <Input type="time" className="w-[140px] bg-background" value={timeTo} onChange={(e) => setTimeTo(e.target.value)} />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Контрагент (опционально)</div>
                      <Input
                        className="w-full sm:w-[320px] bg-background"
                        placeholder='Например: ООО "Альбион 2002"'
                        value={clientName}
                        onChange={(e) => setClientName(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Код события</div>
                      <EventCodeCombobox value={eventCode} onChange={setEventCode} />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Поиск по объекту (опционально)</div>
                      <Input
                        className="w-full sm:w-[520px] bg-background"
                        placeholder="Название / адрес / ID"
                        value={objectQuery}
                        onChange={(e) => setObjectQuery(e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ) : null}

              {createKind === 'gbrRaportXlsx' ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Период</div>
                      <QuickRangeButtons />
                      <div className="flex flex-wrap items-end gap-2">
                        <DateRangePicker
                          value={dateRange}
                          onChange={setDateRange}
                          placeholder="Выберите период"
                          triggerClassName="w-[280px]"
                          numberOfMonths={2}
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Время (от/до)</div>
                      <div className="flex items-center gap-2">
                        <Input type="time" className="w-[140px] bg-background" value={timeFrom} onChange={(e) => setTimeFrom(e.target.value)} />
                        <div className="text-muted-foreground">—</div>
                        <Input type="time" className="w-[140px] bg-background" value={timeTo} onChange={(e) => setTimeTo(e.target.value)} />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">ГБР</div>
                      <Select value={String(gbrName)} onValueChange={(v) => setGbrName(v)}>
                        <SelectTrigger className="w-[260px] bg-background">
                          <SelectValue placeholder="ГБР" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">Все ГБР</SelectItem>
                          {(analyticsFilters?.gbrNames || []).map((g) => (
                            <SelectItem key={g} value={g}>
                              {g}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">№ объекта (Panel_id)</div>
                      <Input
                        className="w-[220px] bg-background"
                        placeholder="ObjectId"
                        value={gbrObjectId}
                        onChange={(e) => setGbrObjectId(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="secondary" size="sm" onClick={loadGbrPreview} disabled={gbrPreviewLoading}>
                      {gbrPreviewLoading ? 'Загрузка…' : 'Предпросмотр'}
                    </Button>
                    <Button variant="outline" size="sm" onClick={downloadGbrRaportXlsx}>
                      Скачать XLSX
                    </Button>
                  </div>

                  <div className="rounded-md border border-border">
                    <ScrollArea className="h-[280px]">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                          <tr>
                            <th className="text-left font-medium px-3 py-2">№ объекта</th>
                            <th className="text-left font-medium px-3 py-2">Адрес/объект</th>
                            <th className="text-left font-medium px-3 py-2">ГБР</th>
                            <th className="text-left font-medium px-3 py-2">Вызов</th>
                            <th className="text-left font-medium px-3 py-2">Прибыл</th>
                            <th className="text-right font-medium px-3 py-2">В пути</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(gbrPreview || []).map((r) => (
                            <tr key={`${r.eventId}:${r.gbrName}:${r.calledAt || ''}`} className="border-t border-border">
                              <td className="px-3 py-2 font-mono">{r.objectId || '—'}</td>
                              <td className="px-3 py-2">
                                <div className="text-foreground">{r.objectName || '—'}</div>
                                <div className="text-xs text-muted-foreground">{r.clientName || ''}</div>
                              </td>
                              <td className="px-3 py-2">{r.gbrName}</td>
                              <td className="px-3 py-2 tabular-nums">{r.calledAt ? r.calledAt.replace('T', ' ').slice(0, 19) : '—'}</td>
                              <td className="px-3 py-2 tabular-nums">{r.arrivedAt ? r.arrivedAt.replace('T', ' ').slice(0, 19) : (r.cancelledAt ? 'Отмена' : '—')}</td>
                              <td className="px-3 py-2 text-right tabular-nums">{r.travelSeconds == null ? '—' : Math.round(r.travelSeconds)}</td>
                            </tr>
                          ))}
                          {!gbrPreviewLoading && (gbrPreview || []).length === 0 && (
                            <tr>
                              <td className="px-3 py-6 text-muted-foreground" colSpan={6}>
                                Нет данных по выбранным фильтрам
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </ScrollArea>
                  </div>
                </div>
              ) : null}

              {createKind === 'eventsRaportXlsx' || createKind === 'alarmMessages' ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Период</div>
                      <QuickRangeButtons />
                      <div className="flex flex-wrap items-end gap-2">
                        <DateRangePicker
                          value={dateRange}
                          onChange={setDateRange}
                          placeholder="Выберите период"
                          triggerClassName="w-[280px]"
                          numberOfMonths={2}
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Время (от/до)</div>
                      <div className="flex items-center gap-2">
                        <Input type="time" className="w-[140px] bg-background" value={timeFrom} onChange={(e) => setTimeFrom(e.target.value)} />
                        <div className="text-muted-foreground">—</div>
                        <Input type="time" className="w-[140px] bg-background" value={timeTo} onChange={(e) => setTimeTo(e.target.value)} />
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Поиск (опционально)</div>
                      <Input
                        className="w-full sm:w-[520px] bg-background"
                        placeholder="Описание / объект / контрагент / адрес"
                        value={eventsSearch}
                        onChange={(e) => setEventsSearch(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">№ объекта (Panel_id) (опционально)</div>
                      <Input
                        className="w-[220px] bg-background"
                        placeholder="ObjectId"
                        value={eventsObjectId}
                        onChange={(e) => setEventsObjectId(e.target.value)}
                      />
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Тип</div>
                      <Select value={String(eventsType)} onValueChange={(v) => setEventsType(v as any)}>
                        <SelectTrigger className="w-[200px] bg-background">
                          <SelectValue placeholder="Тип" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">Все типы</SelectItem>
                          <SelectItem value="intrusion">Проникновение</SelectItem>
                          <SelectItem value="alarm">Тревога</SelectItem>
                          <SelectItem value="access">Доступ</SelectItem>
                          <SelectItem value="patrol">Обход</SelectItem>
                          <SelectItem value="incident">Инцидент</SelectItem>
                          <SelectItem value="maintenance">ТО</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Серьёзность</div>
                      <Select value={String(eventsSeverity)} onValueChange={(v) => setEventsSeverity(v as any)}>
                        <SelectTrigger className="w-[200px] bg-background">
                          <SelectValue placeholder="Серьёзность" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">Все уровни</SelectItem>
                          <SelectItem value="critical">Критический</SelectItem>
                          <SelectItem value="warning">Внимание</SelectItem>
                          <SelectItem value="info">Информация</SelectItem>
                          <SelectItem value="success">Норма</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Статус</div>
                      <Select value={String(eventsStatus)} onValueChange={(v) => setEventsStatus(v as any)}>
                        <SelectTrigger className="w-[200px] bg-background">
                          <SelectValue placeholder="Статус" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">Все статусы</SelectItem>
                          <SelectItem value="active">Активно</SelectItem>
                          <SelectItem value="pending">В обработке</SelectItem>
                          <SelectItem value="resolved">Завершено</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-5 pt-1">
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="eventsOnlyWithOperatorComment"
                        checked={eventsOnlyWithOperatorComment}
                        onCheckedChange={(checked) => setEventsOnlyWithOperatorComment(Boolean(checked))}
                      />
                      <Label htmlFor="eventsOnlyWithOperatorComment" className="text-sm">
                        Только с пометкой оператора
                      </Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="eventsIncludeSystem"
                        checked={eventsIncludeSystem}
                        onCheckedChange={(checked) => setEventsIncludeSystem(Boolean(checked))}
                      />
                      <Label htmlFor="eventsIncludeSystem" className="text-sm">
                        Включая системные
                      </Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="eventsIncludeCancelled"
                        checked={eventsIncludeCancelled}
                        onCheckedChange={(checked) => setEventsIncludeCancelled(Boolean(checked))}
                      />
                      <Label htmlFor="eventsIncludeCancelled" className="text-sm">
                        Включая отменённые
                      </Label>
                    </div>
                  </div>
                </div>
              ) : null}

              {createKind === 'pcnLedger' ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Период</div>
                      <QuickRangeButtons />
                      <div className="flex flex-wrap items-end gap-2">
                        <DateRangePicker
                          value={dateRange}
                          onChange={setDateRange}
                          placeholder="Выберите период"
                          triggerClassName="w-[280px]"
                          numberOfMonths={2}
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Время (от/до)</div>
                      <div className="flex items-center gap-2">
                        <Input type="time" className="w-[140px] bg-background" value={timeFrom} onChange={(e) => setTimeFrom(e.target.value)} />
                        <div className="text-muted-foreground">—</div>
                        <Input type="time" className="w-[140px] bg-background" value={timeTo} onChange={(e) => setTimeTo(e.target.value)} />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Оператор (опционально)</div>
                      <Input
                        className="w-[320px] bg-background"
                        placeholder="ФИО или часть"
                        value={pcnOperatorQuery}
                        onChange={(e) => setPcnOperatorQuery(e.target.value)}
                      />
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Персональные данные</div>
                      <div className="flex items-center gap-2 h-10">
                        <Checkbox
                          id="pcnHideOperatorNames"
                          checked={pcnHideOperatorNames}
                          onCheckedChange={(v) => setPcnHideOperatorNames(Boolean(v))}
                        />
                        <Label htmlFor="pcnHideOperatorNames" className="text-sm">
                          Без фамилий (скрыть ФИО)
                        </Label>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-md border border-border p-3 space-y-3">
                    <div className="text-sm font-medium text-foreground">Пороги и выплаты (можно менять)</div>

                    <div className="flex flex-wrap items-end gap-3">
                      <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">Выплата 0</div>
                        <Input type="number" className="w-[120px] bg-background" value={pcnPay0} onChange={(e) => setPcnPay0(e.target.value)} />
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">Выплата 1</div>
                        <Input type="number" className="w-[120px] bg-background" value={pcnPay1} onChange={(e) => setPcnPay1(e.target.value)} />
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">Выплата 2</div>
                        <Input type="number" className="w-[120px] bg-background" value={pcnPay2} onChange={(e) => setPcnPay2(e.target.value)} />
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">Выплата 3</div>
                        <Input type="number" className="w-[120px] bg-background" value={pcnPay3} onChange={(e) => setPcnPay3(e.target.value)} />
                      </div>
                    </div>

                    <div className="flex flex-wrap items-end gap-6">
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-muted-foreground">3 диспетчера (t1/t2/t3)</div>
                        <div className="flex items-end gap-2">
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr3_1} onChange={(e) => setPcnThr3_1(e.target.value)} />
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr3_2} onChange={(e) => setPcnThr3_2(e.target.value)} />
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr3_3} onChange={(e) => setPcnThr3_3(e.target.value)} />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="text-xs font-medium text-muted-foreground">4 диспетчера (t1/t2/t3)</div>
                        <div className="flex items-end gap-2">
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr4_1} onChange={(e) => setPcnThr4_1(e.target.value)} />
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr4_2} onChange={(e) => setPcnThr4_2(e.target.value)} />
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr4_3} onChange={(e) => setPcnThr4_3(e.target.value)} />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="text-xs font-medium text-muted-foreground">5 диспетчеров (t1/t2/t3)</div>
                        <div className="flex items-end gap-2">
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr5_1} onChange={(e) => setPcnThr5_1(e.target.value)} />
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr5_2} onChange={(e) => setPcnThr5_2(e.target.value)} />
                          <Input type="number" className="w-[90px] bg-background" value={pcnThr5_3} onChange={(e) => setPcnThr5_3(e.target.value)} />
                        </div>
                      </div>
                    </div>

                    <div className="text-xs text-muted-foreground">
                      Пороги должны быть по возрастанию (0–100). Эти значения будут напечатаны в шапке XLSX как правило расчёта.
                    </div>
                  </div>

                  <div className="text-xs text-muted-foreground">
                    Тревоги считаются по действиям оператора «Прием на обработку». Пороговые выплаты берутся как в шаблоне.
                  </div>
                </div>
              ) : null}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>
                Отмена
              </Button>
              <Button
                onClick={() => {
                  toast({ title: 'Отчёт', description: 'Формирование…' });
                  createReportInHistory();
                }}
              >
                Сформировать
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Table */}
        <ReportsTable reports={filteredReports} onChanged={refetch} />
      </div>
    </MainLayout>
  );
}
