import { Report, ReportType, ReportStatus } from '@/types';
import { cn } from '@/lib/utils';
import { apiFetchRaw, apiGet, apiPost } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { ArrowLeftRight, Columns2, Download, Eye, FileText, MoreHorizontal, ZoomIn, ZoomOut } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { GbrTripRow, GbrTripsResponse } from '@/types';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

type ReportParamsResponse = Report & {
  params?: Record<string, any>;
};

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function reorder<T>(arr: T[], from: number, to: number): T[] {
  const out = arr.slice();
  const [x] = out.splice(from, 1);
  out.splice(to, 0, x);
  return out;
}

function reorderRows(rows: string[][], from: number, to: number): string[][] {
  return rows.map((r) => reorder(r, from, to));
}

function parseSortableCellValue(value: string): number | string {
  const text = String(value || '').trim();
  if (!text || text === '—') return '';

  const isoCandidate = text.includes(' ') ? text.replace(' ', 'T') : text;
  const isoTs = Date.parse(isoCandidate);
  if (!Number.isNaN(isoTs)) return isoTs;

  const ruDateMatch = text.match(/^(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/);
  if (ruDateMatch) {
    const [, dd, mm, yyyy, hh = '00', min = '00', ss = '00'] = ruDateMatch;
    const ruTs = Date.UTC(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh), Number(min), Number(ss));
    if (!Number.isNaN(ruTs)) return ruTs;
  }

  const numericCandidate = text.replace(/\s+/g, '').replace(',', '.');
  if (/^-?\d+(?:\.\d+)?$/.test(numericCandidate)) {
    const parsedNumber = Number(numericCandidate);
    if (!Number.isNaN(parsedNumber)) return parsedNumber;
  }

  return text.toLocaleLowerCase('ru');
}

function compareTableCells(a: string, b: string): number {
  const left = parseSortableCellValue(a);
  const right = parseSortableCellValue(b);

  if (left === '' && right === '') return 0;
  if (left === '') return 1;
  if (right === '') return -1;

  if (typeof left === 'number' && typeof right === 'number') {
    return left - right;
  }

  return String(left).localeCompare(String(right), 'ru', { numeric: true, sensitivity: 'base' });
}

function SheetViewer({
  titleLines,
  columns,
  rows,
  loading,
}: {
  titleLines: string[];
  columns: string[];
  rows: string[][];
  loading: boolean;
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [viewColumns, setViewColumns] = useState<string[]>([]);
  const [viewRows, setViewRows] = useState<string[][]>([]);
  const [colWidths, setColWidths] = useState<number[]>([]);
  const [zoom, setZoom] = useState<number>(100);
  const [sortState, setSortState] = useState<{ index: number; direction: 'asc' | 'desc' } | null>(null);
  const dragFromRef = useRef<number | null>(null);

  useEffect(() => {
    setViewColumns(columns || []);
    setViewRows(rows || []);
    const base = (columns || []).map((c) => clamp(Math.max(120, String(c || '').length * 10), 90, 420));
    setColWidths(base);
    setZoom(100);
    setSortState(null);
  }, [columns, rows]);

  const totalWidth = useMemo(() => colWidths.reduce((a, b) => a + (b || 0), 0), [colWidths]);

  const fitToWidth = () => {
    const el = viewportRef.current;
    if (!el) return;
    const w = el.clientWidth;
    if (!w || !totalWidth) return;
    const target = (w - 48) / totalWidth;
    const pct = clamp(Math.round(target * 100), 30, 200);
    setZoom(pct);
  };

  useEffect(() => {
    if (!viewColumns.length) return;
    const raf = window.requestAnimationFrame(() => fitToWidth());
    return () => window.cancelAnimationFrame(raf);
  }, [viewColumns.length, totalWidth]);

  const onStartResize = (idx: number, e: any) => {
    e.preventDefault?.();
    e.stopPropagation?.();
    const startX = Number(e.clientX || 0);
    const startW = colWidths[idx] ?? 120;

    const onMove = (ev: PointerEvent) => {
      const dx = ev.clientX - startX;
      setColWidths((prev) => {
        const next = prev.slice();
        next[idx] = clamp(startW + dx, 60, 900);
        return next;
      });
    };

    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const onDragStartHeader = (idx: number) => {
    dragFromRef.current = idx;
  };

  const onDropHeader = (toIdx: number) => {
    const fromIdx = dragFromRef.current;
    dragFromRef.current = null;
    if (fromIdx == null || fromIdx === toIdx) return;
    setViewColumns((prev) => reorder(prev, fromIdx, toIdx));
    setColWidths((prev) => reorder(prev, fromIdx, toIdx));
    setViewRows((prev) => reorderRows(prev, fromIdx, toIdx));
    setSortState((prev) => {
      if (!prev) return prev;
      if (prev.index === fromIdx) return { ...prev, index: toIdx };
      if (fromIdx < prev.index && prev.index <= toIdx) return { ...prev, index: prev.index - 1 };
      if (toIdx <= prev.index && prev.index < fromIdx) return { ...prev, index: prev.index + 1 };
      return prev;
    });
  };

  const sortByColumn = (index: number) => {
    setSortState((prev) => {
      const direction = prev && prev.index === index && prev.direction === 'asc' ? 'desc' : 'asc';
      setViewRows((currentRows) => {
        const sortedRows = currentRows.slice().sort((left, right) => {
          const result = compareTableCells(left?.[index] || '', right?.[index] || '');
          return direction === 'asc' ? result : -result;
        });
        return sortedRows;
      });
      return { index, direction };
    });
  };

  const zoomStyle: any = useMemo(() => ({ zoom: zoom / 100 }), [zoom]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => setZoom((z) => clamp(z - 10, 30, 200))}
          >
            <ZoomOut className="h-4 w-4" />
            −
          </Button>
          <div className="w-[160px]">
            <Slider
              value={[zoom]}
              min={30}
              max={200}
              step={5}
              onValueChange={(v) => setZoom(clamp(Number(v?.[0] ?? 100), 30, 200))}
            />
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => setZoom((z) => clamp(z + 10, 30, 200))}
          >
            <ZoomIn className="h-4 w-4" />
            +
          </Button>
          <div className="text-sm text-muted-foreground tabular-nums w-[64px] text-right">{zoom}%</div>
        </div>

        <div className="flex items-center gap-2">
          <Button type="button" variant="secondary" size="sm" className="gap-2" onClick={fitToWidth}>
            <Columns2 className="h-4 w-4" />
            Вписать
          </Button>
          <div className="text-xs text-muted-foreground hidden sm:flex items-center gap-1">
            <ArrowLeftRight className="h-3.5 w-3.5" />
            Клик по заголовку сортирует, перетаскивание меняет порядок столбцов
          </div>
        </div>
      </div>

      <div className="rounded-md border border-border bg-muted/30">
        <div ref={viewportRef} className="max-h-[78dvh] w-full overflow-auto p-3 sm:p-6">
          <div className="mx-auto w-fit" style={zoomStyle}>
            <div className="rounded-md border border-border bg-background">
              <div className="p-4 border-b border-border space-y-1">
                {(titleLines || []).slice(0, 8).map((t, i) => (
                  <div key={i} className={cn('text-sm', i === 0 ? 'font-semibold text-foreground' : 'text-muted-foreground')}>
                    {t}
                  </div>
                ))}
              </div>

              <div className="overflow-auto">
                {loading ? (
                  <div className="p-4 text-sm text-muted-foreground">Загрузка…</div>
                ) : viewColumns.length === 0 ? (
                  <div className="p-4 text-sm text-muted-foreground">Нет данных</div>
                ) : (
                  <table className="text-sm">
                    <colgroup>
                      {viewColumns.map((_, i) => (
                        <col key={i} style={{ width: colWidths[i] ?? 120 }} />
                      ))}
                    </colgroup>
                    <thead>
                      <tr className="border-b border-border bg-muted/40">
                        {viewColumns.map((c, idx) => (
                          <th
                            key={`${c}-${idx}`}
                            className="relative text-left font-medium px-3 py-2 whitespace-nowrap select-none"
                            draggable
                            onDragStart={() => onDragStartHeader(idx)}
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={() => onDropHeader(idx)}
                            title="Перетащите, чтобы поменять порядок"
                          >
                            <button
                              type="button"
                              className="max-w-[calc(100%-0.5rem)] truncate pr-3 text-left"
                              onClick={() => sortByColumn(idx)}
                              title="Нажмите, чтобы отсортировать"
                            >
                              {c || ''}
                              {sortState?.index === idx ? (sortState.direction === 'asc' ? ' ^' : ' v') : ''}
                            </button>
                            <div
                              className="absolute right-0 top-0 h-full w-2 cursor-col-resize"
                              onPointerDown={(e) => onStartResize(idx, e)}
                              title="Потяните, чтобы изменить ширину"
                            />
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {viewRows.map((r, i) => (
                        <tr key={i} className="border-b border-border last:border-b-0">
                          {viewColumns.map((_, j) => (
                            <td key={j} className="px-3 py-2 align-top whitespace-pre-wrap break-words">
                              {r?.[j] ? r[j] : '—'}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface ReportsTableProps {
  reports: Report[];
  onChanged?: () => void;
}

const typeLabels: Record<ReportType, string> = {
  weekly: 'Недельный',
  monthly: 'Месячный',
  objectsByCode: 'Объекты по коду',
  gbrRaportXlsx: 'Рапорт (ГБР)',
  eventsRaportXlsx: 'Рапорт по событиям',
  alarmMessages: 'Тревожные сообщения',
  pcnLedger: 'Ведомость по тревогам (ПЦН)',
};

const statusLabels: Record<ReportStatus, string> = {
  generated: 'Сформирован',
  sent: 'Отправлен',
  pending: 'Ожидает',
  failed: 'Ошибка',
};

const statusStyles: Record<ReportStatus, string> = {
  generated: 'bg-severity-info/10 text-severity-info border-severity-info/30',
  sent: 'bg-severity-success/10 text-severity-success border-severity-success/30',
  pending: 'bg-severity-warning/10 text-severity-warning border-severity-warning/30',
  failed: 'bg-severity-critical/10 text-severity-critical border-severity-critical/30',
};

export function ReportsTable({ reports, onChanged }: ReportsTableProps) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTitle, setPreviewTitle] = useState('');
  const [previewRows, setPreviewRows] = useState<GbrTripRow[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [tableColumns, setTableColumns] = useState<string[]>([]);
  const [tableRows, setTableRows] = useState<string[][]>([]);
  const [tableTitleLines, setTableTitleLines] = useState<string[]>([]);
  const [previewSheets, setPreviewSheets] = useState<string[]>([]);
  const [previewSheetName, setPreviewSheetName] = useState('');
  const [previewMode, setPreviewMode] = useState<'none' | 'gbr' | 'table'>('none');

  const humanizeColumn = (c: string) => {
    const s = String(c || '').trim();
    if (!s) return s;
    const map: Record<string, string> = {
      object_no: 'Номер объекта',
      object_number: 'Номер объекта',
      object: 'Номер объекта',
      Panel_ID: 'Номер объекта',
      Panel_id: 'Номер объекта',
      panel_id: 'Номер объекта',
      object_id: 'Номер объекта',
      objectId: 'Номер объекта',

      Object_name: 'Название объекта',
      object_name: 'Название объекта',
      objectName: 'Название объекта',
      'Object name': 'Название объекта',

      client: 'Контрагент',
      client_name: 'Контрагент',
      clientName: 'Контрагент',

      addr: 'Адрес',
      location: 'Адрес',
      address: 'Адрес',

      events: 'Количество тревог',
      events_count: 'Количество тревог',
      eventsCount: 'Количество тревог',

      event_code: 'Код события',
      eventCode: 'Код события',
      code: 'Код события',

      event_code_text: 'Событие',
      eventCodeText: 'Событие',
      code_text: 'Событие',
      codeText: 'Событие',

      first_time: 'Первое срабатывание',
      firstTime: 'Первое срабатывание',
      last_time: 'Последнее срабатывание',
      lastTime: 'Последнее срабатывание',

      result_text: 'Пометка оператора',
      resultText: 'Пометка оператора',
      note: 'Пометка оператора',
      operator_note: 'Пометка оператора',
      operatorNote: 'Пометка оператора',

      timestamp: 'Дата/время',
      TimeEvent: 'Дата/время',

      severity: 'Важность',
      status: 'Статус',
      description: 'Описание',
    };
    return map[s] || s;
  };

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Report | null>(null);

  const [paramsOpen, setParamsOpen] = useState(false);
  const [paramsLoading, setParamsLoading] = useState(false);
  const [paramsTitle, setParamsTitle] = useState('Параметры отчёта');
  const [paramsText, setParamsText] = useState('');

  const formatDate = (dateString: string) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  const formatDateTime = (dateString: string) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

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

  const replaceExt = (name: string, ext: 'xlsx') => {
    const base = name.replace(/\.(csv|xlsx)$/i, '');
    return `${base}.${ext}`;
  };

  const isStoredReport = (report: Report) => {
    // Stored reports have UUID-like ids and downloadUrl /reports/{id}/download
    if (!report.generatedAt) return false;
    if (!report.downloadUrl) return false;
    return report.downloadUrl.startsWith('/reports/') && report.downloadUrl.includes('/download');
  };

  const canDeleteReport = (report: Report) => {
    return Boolean(report.id && report.generatedAt);
  };

  const openPreview = async (report: Report, requestedSheetName?: string) => {
    setPreviewTitle(report.title || typeLabels[report.type] || 'Отчёт');
    setPreviewOpen(true);
    setPreviewLoading(true);
    setPreviewRows([]);
    setTableColumns([]);
    setTableRows([]);
    setTableTitleLines([]);
    setPreviewSheets([]);
    setPreviewMode('none');
    try {
      if (isStoredReport(report)) {
        const params = new URLSearchParams();
        params.set('maxRows', '1000');
        params.set('maxCols', '80');
        const preferredSheet = requestedSheetName || (report.type === 'pcnLedger' ? 'Тревоги по операторам' : '');
        if (preferredSheet) params.set('sheetName', preferredSheet);
        const res = await apiFetchRaw(
          `/reports/${encodeURIComponent(report.id)}/preview?${params.toString()}`,
        );
        const json = (await res.json()) as any;

        if (json?.kind === 'gbr') {
          setPreviewMode('gbr');
          const data = json as GbrTripsResponse;
          setPreviewRows(data?.data || []);
          return;
        }

        setPreviewMode('table');
        setTableColumns(Array.isArray(json?.columns) ? json.columns.map(humanizeColumn) : []);
        setTableRows(Array.isArray(json?.rows) ? json.rows : []);
        setTableTitleLines(Array.isArray(json?.titleLines) ? json.titleLines : []);
        setPreviewSheets(Array.isArray(json?.sheets) ? json.sheets : []);
        setPreviewSheetName(String(json?.sheetName || preferredSheet || ''));
        return;
      }

      // Derived reports: preview is not supported (we only keep XLSX downloads).
      toast({
        title: 'Просмотр отчёта',
        description: 'Предпросмотр доступен только для отчётов из истории. Скачайте XLSX для просмотра.',
      });
      setPreviewMode('none');
      setTableColumns([]);
      setTableRows([]);
    } catch (e: any) {
      toast({
        title: 'Просмотр отчёта',
        description: e?.message || 'Ошибка загрузки предпросмотра',
        variant: 'destructive',
      });
    } finally {
      setPreviewLoading(false);
    }
  };

  const downloadReportXlsx = async (report: Report) => {
    // Stored reports: always go through /reports/{id}/download?format=xlsx
    if (isStoredReport(report)) {
      const url = `/reports/${encodeURIComponent(report.id)}/download?format=xlsx`;
      const fileBase = report.fileName || `report-${report.id}.xlsx`;
      const file = replaceExt(fileBase, 'xlsx');
      await downloadBlob(url, file);
      return;
    }

    // Fallback: if backend gave direct URL, try it as-is
    if (report.downloadUrl) {
      const file = report.fileName || 'report.xlsx';
      await downloadBlob(report.downloadUrl, file);
      return;
    }

    toast({ title: 'Скачать', description: 'Для этого отчёта нет файла.' });
  };

  const confirmDelete = (report: Report) => {
    setDeleteTarget(report);
    setDeleteOpen(true);
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    try {
      await apiFetchRaw(`/reports/${encodeURIComponent(deleteTarget.id)}`, { method: 'DELETE' });
      toast({ title: 'Отчёт', description: 'Удалено.' });
      setDeleteOpen(false);
      setDeleteTarget(null);
      onChanged?.();
    } catch (e: any) {
      toast({
        title: 'Удаление',
        description: e?.message || 'Не удалось удалить отчёт',
        variant: 'destructive',
      });
    }
  };

  const fetchReportParams = async (report: Report): Promise<ReportParamsResponse> => {
    return await apiGet<ReportParamsResponse>(`/reports/${encodeURIComponent(report.id)}/params`);
  };

  const viewReportParams = async (report: Report) => {
    setParamsOpen(true);
    setParamsLoading(true);
    setParamsTitle(`Параметры отчёта: ${report.title || report.type}`);
    setParamsText('');
    try {
      const data = await fetchReportParams(report);
      const text = JSON.stringify(data?.params || {}, null, 2);
      setParamsText(text || '{}');
    } catch (e: any) {
      toast({
        title: 'Параметры отчёта',
        description: e?.message || 'Не удалось загрузить параметры',
        variant: 'destructive',
      });
      setParamsText('');
    } finally {
      setParamsLoading(false);
    }
  };

  const toSearchParams = (paramsObj: Record<string, any> | undefined, fallback: Partial<Report>) => {
    const params = new URLSearchParams();
    const src: Record<string, any> = { ...(paramsObj || {}) };

    // Defensive: ensure period fields exist for date-range based reports.
    if (fallback.periodStart && src.dateFrom == null) src.dateFrom = fallback.periodStart;
    if (fallback.periodEnd && src.dateTo == null) src.dateTo = fallback.periodEnd;

    for (const [k, v] of Object.entries(src)) {
      if (v == null) continue;
      if (Array.isArray(v)) {
        for (const item of v) {
          if (item == null) continue;
          const s = String(item).trim();
          if (!s) continue;
          params.append(k, s);
        }
        continue;
      }
      if (typeof v === 'boolean') {
        if (v) params.set(k, 'true');
        continue;
      }
      const s = String(v).trim();
      if (!s) continue;
      params.set(k, s);
    }
    return params;
  };

  const regenerateReport = async (report: Report) => {
    try {
      const data = await fetchReportParams(report);
      const params = toSearchParams(data?.params, report);

      let path = '';
      switch (report.type) {
        case 'objectsByCode':
          path = `/reports/generate/objects-by-code?${params.toString()}`;
          break;
        case 'gbrRaportXlsx':
          path = `/reports/generate/gbr-raport-xlsx?${params.toString()}`;
          break;
        case 'eventsRaportXlsx':
          path = `/reports/generate/events-raport-xlsx?${params.toString()}`;
          break;
        case 'alarmMessages':
          path = `/reports/generate/alarm-messages-xlsx?${params.toString()}`;
          break;
        case 'pcnLedger':
          path = `/reports/generate/pcn-ledger-xlsx?${params.toString()}`;
          break;
        default:
          toast({ title: 'Перегенерация', description: 'Неизвестный тип отчёта', variant: 'destructive' });
          return;
      }

      await apiPost(path);
      toast({ title: 'Перегенерация', description: 'Запущено. Новый отчёт появится в истории.' });
      onChanged?.();
    } catch (e: any) {
      toast({
        title: 'Перегенерация',
        description: e?.message || 'Не удалось перегенерировать отчёт',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <Dialog open={paramsOpen} onOpenChange={setParamsOpen}>
        <DialogContent fullscreenable className="sm:max-w-[720px]">
          <DialogHeader>
            <DialogTitle>{paramsTitle}</DialogTitle>
          </DialogHeader>
          <div className="text-sm text-muted-foreground">
            {paramsLoading ? (
              'Загрузка…'
            ) : paramsText ? (
              <pre className="whitespace-pre-wrap break-words rounded-md border border-border bg-muted/30 p-3 max-h-[60dvh] overflow-auto">
                {paramsText}
              </pre>
            ) : (
              'Нет параметров.'
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent
          fullscreenable
          defaultFullscreen
          className="w-[98vw] max-w-[1400px] h-[92dvh] overflow-hidden p-3 sm:p-4 flex flex-col"
        >
          <DialogHeader>
            <DialogTitle>{previewTitle}</DialogTitle>
          </DialogHeader>
          <div className="rounded-md border border-border min-h-0 flex-1 overflow-hidden">
            <div className="w-full h-full min-h-0">
              {previewMode === 'none' ? (
                <div className="p-4 text-sm text-muted-foreground">
                  {previewLoading ? 'Загрузка…' : 'Предпросмотр недоступен для этого отчёта. Скачайте XLSX.'}
                </div>
              ) : previewMode === 'gbr' ? (
                <div className="h-full max-h-[80dvh] w-full overflow-x-auto overflow-y-auto">
                  <table className="w-full min-w-[1100px] text-sm">
                    <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                      <tr>
                        <th className="text-left font-medium px-3 py-2 whitespace-nowrap">№ объекта</th>
                        <th className="text-left font-medium px-3 py-2">Адрес/объект</th>
                        <th className="text-left font-medium px-3 py-2 whitespace-nowrap">ГБР</th>
                        <th className="text-left font-medium px-3 py-2 whitespace-nowrap">Вызов</th>
                        <th className="text-left font-medium px-3 py-2 whitespace-nowrap">Прибыл</th>
                        <th className="text-right font-medium px-3 py-2 whitespace-nowrap">В пути (сек)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewRows.map((r) => (
                        <tr key={`${r.eventId}:${r.gbrName}:${r.calledAt || ''}`} className="border-t border-border">
                          <td className="px-3 py-2 font-mono whitespace-nowrap">{r.objectId || '—'}</td>
                          <td className="px-3 py-2 align-top whitespace-normal break-words max-w-[520px]">
                            <div className="text-foreground">{r.objectName || '—'}</div>
                            <div className="text-xs text-muted-foreground">{r.clientName || ''}</div>
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap">{r.gbrName}</td>
                          <td className="px-3 py-2 tabular-nums whitespace-nowrap">{r.calledAt ? r.calledAt.replace('T', ' ').slice(0, 19) : '—'}</td>
                          <td className="px-3 py-2 tabular-nums whitespace-nowrap">{r.arrivedAt ? r.arrivedAt.replace('T', ' ').slice(0, 19) : (r.cancelledAt ? 'Отмена' : '—')}</td>
                          <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">{r.travelSeconds == null ? '—' : Math.round(r.travelSeconds)}</td>
                        </tr>
                      ))}
                      {!previewLoading && previewRows.length === 0 && (
                        <tr>
                          <td className="px-3 py-6 text-muted-foreground" colSpan={6}>
                            Нет данных
                          </td>
                        </tr>
                      )}
                      {previewLoading && (
                        <tr>
                          <td className="px-3 py-6 text-muted-foreground" colSpan={6}>
                            Загрузка…
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="h-full min-h-0 p-2 sm:p-3">
                  {previewSheets.length > 1 ? (
                    <div className="mb-3 flex flex-wrap gap-2">
                      {previewSheets.map((sheet) => (
                        <Button
                          key={sheet}
                          variant={sheet === previewSheetName ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => {
                            if (sheet !== previewSheetName) {
                              const activeReport = reports.find((r) => (r.title || typeLabels[r.type] || 'Отчёт') === previewTitle);
                              if (activeReport) {
                                void openPreview(activeReport, sheet);
                              }
                            }
                          }}
                        >
                          {sheet}
                        </Button>
                      ))}
                    </div>
                  ) : null}
                  <SheetViewer
                    titleLines={tableTitleLines}
                    columns={tableColumns}
                    rows={tableRows}
                    loading={previewLoading}
                  />
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent fullscreenable className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>Удалить отчёт?</DialogTitle>
          </DialogHeader>
          <div className="text-sm text-muted-foreground">
            Отчёт будет удалён из истории. Это действие нельзя отменить.
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Отмена
            </Button>
            <Button variant="destructive" onClick={doDelete}>
              Удалить
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent border-border">
            <TableHead className="text-muted-foreground font-medium">Тип отчёта</TableHead>
            <TableHead className="text-muted-foreground font-medium">Период</TableHead>
            <TableHead className="text-muted-foreground font-medium">Дата генерации</TableHead>
            <TableHead className="text-muted-foreground font-medium">Количество</TableHead>
            <TableHead className="text-muted-foreground font-medium">Критических</TableHead>
            <TableHead className="text-muted-foreground font-medium">Статус</TableHead>
            <TableHead className="w-[150px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {reports.map((report) => (
            <TableRow key={report.id} className="table-row-hover border-border">
              <TableCell>
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium text-foreground">{report.title || typeLabels[report.type]}</span>
                </div>
              </TableCell>
              <TableCell className="font-mono text-sm text-foreground">
                {formatDate(report.periodStart)} — {formatDate(report.periodEnd)}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(report.generatedAt)}
              </TableCell>
              <TableCell className="text-foreground font-medium">
                {report.eventsCount.toLocaleString()}
              </TableCell>
              <TableCell>
                <span className={cn(
                  'font-medium',
                  report.criticalCount > 0 ? 'text-severity-critical' : 'text-muted-foreground'
                )}>
                  {report.criticalCount}
                </span>
              </TableCell>
              <TableCell>
                <Badge className={cn('font-medium border', statusStyles[report.status])}>
                  {statusLabels[report.status]}
                </Badge>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => openPreview(report)}
                  >
                    <Eye className="h-4 w-4" />
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Download className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => {
                          downloadReportXlsx(report);
                        }}
                      >
                        XLSX
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => {
                          viewReportParams(report);
                        }}
                      >
                        Просмотреть параметры
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          regenerateReport(report);
                        }}
                      >
                        Перегенерировать
                      </DropdownMenuItem>

                      {canDeleteReport(report) ? (
                        <DropdownMenuItem
                          onClick={() => {
                            confirmDelete(report);
                          }}
                        >
                          Удалить
                        </DropdownMenuItem>
                      ) : null}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
