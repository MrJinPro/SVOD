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
  onChanged?: () => void;
}

const typeLabels: Record<ReportType, string> = {
  weekly: 'Недельный',
  monthly: 'Месячный',
  objectsByCode: 'Объекты по коду',
  gbrRaportXlsx: 'Рапорт (ГБР)',
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
  const [previewMode, setPreviewMode] = useState<'none' | 'gbr' | 'table'>('none');

  const humanizeColumn = (c: string) => {
    const s = String(c || '').trim();
    if (!s) return s;
    const map: Record<string, string> = {
      Panel_ID: 'Номер объекта',
      Panel_id: 'Номер объекта',
      panel_id: 'Номер объекта',
      object_id: 'Номер объекта',
      objectId: 'Номер объекта',

      Object_name: 'Название объекта',
      object_name: 'Название объекта',
      objectName: 'Название объекта',
      'Object name': 'Название объекта',

      client_name: 'Контрагент',
      clientName: 'Контрагент',

      timestamp: 'Дата/время',
      TimeEvent: 'Дата/время',

      severity: 'Важность',
      status: 'Статус',
      description: 'Описание',
      location: 'Адрес',
      address: 'Адрес',
    };
    return map[s] || s;
  };

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Report | null>(null);

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

  const openPreview = async (report: Report) => {
    setPreviewTitle(report.title || typeLabels[report.type] || 'Отчёт');
    setPreviewOpen(true);
    setPreviewLoading(true);
    setPreviewRows([]);
    setTableColumns([]);
    setTableRows([]);
    setPreviewMode('none');
    try {
      if (isStoredReport(report)) {
        const res = await apiFetchRaw(`/reports/${encodeURIComponent(report.id)}/preview`);
        const json = (await res.json()) as any;

        if (json?.kind === 'gbr' || report.type === 'gbrRaportXlsx') {
          setPreviewMode('gbr');
          const data = json as GbrTripsResponse;
          setPreviewRows(data?.data || []);
          return;
        }

        setPreviewMode('table');
        setTableColumns(Array.isArray(json?.columns) ? json.columns.map(humanizeColumn) : []);
        setTableRows(Array.isArray(json?.rows) ? json.rows : []);
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

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="sm:max-w-[900px] max-w-[calc(100vw-2rem)] overflow-hidden">
          <DialogHeader>
            <DialogTitle>{previewTitle}</DialogTitle>
          </DialogHeader>
          <div className="rounded-md border border-border">
            <ScrollArea className="h-[420px] w-full">
              {previewMode === 'none' ? (
                <div className="p-4 text-sm text-muted-foreground">
                  {previewLoading ? 'Загрузка…' : 'Предпросмотр недоступен для этого отчёта. Скачайте XLSX.'}
                </div>
              ) : previewMode === 'gbr' ? (
                <div className="w-full overflow-x-auto">
                  <table className="w-full min-w-max text-sm">
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
                <div className="w-full overflow-x-auto">
                  <table className="w-full min-w-max text-sm">
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
                            <td key={j} className="px-3 py-2 align-top whitespace-normal break-words max-w-[520px]">
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
                </div>
              )}
            </ScrollArea>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="sm:max-w-[520px]">
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

                      {isStoredReport(report) ? (
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
