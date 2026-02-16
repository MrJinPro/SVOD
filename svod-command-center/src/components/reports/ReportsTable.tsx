import { Report, ReportType, ReportStatus } from '@/types';
import { cn } from '@/lib/utils';
import { apiFetchRaw } from '@/lib/api';
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
import { Download, FileText, Eye, MoreHorizontal } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useState } from 'react';
import type { GbrTripRow, GbrTripsResponse } from '@/types';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface ReportsTableProps {
  reports: Report[];
}

const typeLabels: Record<ReportType, string> = {
  daily: 'Суточный',
  weekly: 'Недельный',
  monthly: 'Месячный',
  objectsByCode: 'Объекты по коду',
  gbrRaportXlsx: 'Рапорт (ГБР)',
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

export function ReportsTable({ reports }: ReportsTableProps) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTitle, setPreviewTitle] = useState('');
  const [previewRows, setPreviewRows] = useState<GbrTripRow[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [tableColumns, setTableColumns] = useState<string[]>([]);
  const [tableRows, setTableRows] = useState<string[][]>([]);
  const [previewMode, setPreviewMode] = useState<'none' | 'gbr' | 'table'>('none');

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

  const parseCsv = (text: string): { columns: string[]; rows: string[][] } => {
    const cleaned = text.replace(/^\uFEFF/, '');
    const lines = cleaned.split(/\r?\n/).filter((l) => l.trim().length > 0);
    if (lines.length === 0) return { columns: [], rows: [] };

    // Simple MVP parser: delimiter ';', no quoted fields support.
    const splitLine = (line: string) => line.split(';').map((x) => x.trim());
    const columns = splitLine(lines[0]);
    const rows = lines.slice(1, 201).map(splitLine);
    return { columns, rows };
  };

  const openPreview = async (report: Report) => {
    setPreviewTitle(typeLabels[report.type] || 'Отчёт');
    setPreviewOpen(true);
    setPreviewLoading(true);
    setPreviewRows([]);
    setTableColumns([]);
    setTableRows([]);
    setPreviewMode('none');
    try {
      if (report.type === 'gbrRaportXlsx') {
        setPreviewMode('gbr');
        const res = await apiFetchRaw(`/reports/${encodeURIComponent(report.id)}/preview`);
        const data = (await res.json()) as GbrTripsResponse;
        setPreviewRows(data?.data || []);
        return;
      }

      // CSV previews
      setPreviewMode('table');
      let path: string | null = null;
      if (report.downloadUrl) {
        path = report.downloadUrl;
      } else if (report.type === 'daily') {
        path = `/reports/export/daily?date=${encodeURIComponent(report.periodStart)}`;
      }

      if (!path) {
        toast({ title: 'Просмотр отчёта', description: 'Для этого отчёта нет данных для предпросмотра.' });
        setTableColumns([]);
        setTableRows([]);
        return;
      }

      const res = await apiFetchRaw(path);
      const text = await res.text();
      const parsed = parseCsv(text);
      setTableColumns(parsed.columns);
      setTableRows(parsed.rows);
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

  const downloadReport = async (report: Report) => {
    const url = report.downloadUrl || null;
    if (!url) {
      // fallback for derived daily
      if (report.type === 'daily') {
        const file = report.fileName || `daily-report-${report.periodStart}.csv`;
        await downloadBlob(`/reports/export/daily?date=${encodeURIComponent(report.periodStart)}`, file);
        return;
      }
      toast({ title: 'Скачать', description: 'Для этого отчёта нет файла.' });
      return;
    }
    const file = report.fileName || 'report.bin';
    await downloadBlob(url, file);
  };

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="sm:max-w-[900px]">
          <DialogHeader>
            <DialogTitle>{previewTitle}</DialogTitle>
          </DialogHeader>
          <div className="rounded-md border border-border">
            <ScrollArea className="h-[420px]">
              {previewMode === 'gbr' ? (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                    <tr>
                      <th className="text-left font-medium px-3 py-2">№ объекта</th>
                      <th className="text-left font-medium px-3 py-2">Адрес/объект</th>
                      <th className="text-left font-medium px-3 py-2">ГБР</th>
                      <th className="text-left font-medium px-3 py-2">Вызов</th>
                      <th className="text-left font-medium px-3 py-2">Прибыл</th>
                      <th className="text-right font-medium px-3 py-2">В пути (сек)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewRows.map((r) => (
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
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                    <tr>
                      {(tableColumns.length ? tableColumns : ['']).map((c, idx) => (
                        <th key={`${c}-${idx}`} className="text-left font-medium px-3 py-2 whitespace-nowrap">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map((r, i) => (
                      <tr key={i} className="border-t border-border">
                        {(r.length ? r : ['']).map((v, j) => (
                          <td key={j} className="px-3 py-2 align-top whitespace-nowrap">
                            {v || '—'}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {!previewLoading && tableRows.length === 0 && (
                      <tr>
                        <td className="px-3 py-6 text-muted-foreground" colSpan={Math.max(1, tableColumns.length || 1)}>
                          Нет данных
                        </td>
                      </tr>
                    )}
                    {previewLoading && (
                      <tr>
                        <td className="px-3 py-6 text-muted-foreground" colSpan={Math.max(1, tableColumns.length || 1)}>
                          Загрузка…
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              )}
            </ScrollArea>
          </div>
        </DialogContent>
      </Dialog>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent border-border">
            <TableHead className="text-muted-foreground font-medium">Тип отчёта</TableHead>
            <TableHead className="text-muted-foreground font-medium">Период</TableHead>
            <TableHead className="text-muted-foreground font-medium">Дата генерации</TableHead>
            <TableHead className="text-muted-foreground font-medium">Событий</TableHead>
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
                  <span className="font-medium text-foreground">{typeLabels[report.type]}</span>
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
                          downloadReport(report);
                        }}
                      >
                        Скачать
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
                          toast({ title: 'Параметры отчёта', description: 'Скоро добавим.' });
                        }}
                      >
                        Просмотреть параметры
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          toast({ title: 'Перегенерация', description: 'Скоро добавим.' });
                        }}
                      >
                        Перегенерировать
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          toast({ title: 'Отправка', description: 'Скоро добавим.' });
                        }}
                      >
                        Отправить повторно
                      </DropdownMenuItem>
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
