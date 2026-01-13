import { Report, ReportType, ReportStatus } from '@/types';
import { cn } from '@/lib/utils';
import { API_BASE_URL } from '@/lib/api';
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

  const downloadDailyCsv = (date: string) => {
    const url = `${API_BASE_URL}/reports/export/daily?date=${encodeURIComponent(date)}`;
    window.location.href = url;
  };

  const prototypeAction = (title: string) =>
    toast({
      title,
      description: 'Действие будет расширено в следующей версии прототипа.',
    });

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
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
                    onClick={() => prototypeAction('Просмотр отчёта')}
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
                          toast({
                            title: 'Экспорт',
                            description: 'В прототипе доступен экспорт в CSV.',
                          });
                          downloadDailyCsv(report.periodStart);
                        }}
                      >
                        Скачать PDF
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          toast({
                            title: 'Экспорт',
                            description: 'В прототипе доступен экспорт в CSV.',
                          });
                          downloadDailyCsv(report.periodStart);
                        }}
                      >
                        Скачать Excel
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          toast({
                            title: 'Экспорт',
                            description: 'В прототипе доступен экспорт в CSV.',
                          });
                          downloadDailyCsv(report.periodStart);
                        }}
                      >
                        Скачать Word
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
                      <DropdownMenuItem onClick={() => prototypeAction('Параметры отчёта')}>
                        Просмотреть параметры
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => prototypeAction('Перегенерация отчёта')}>
                        Перегенерировать
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => prototypeAction('Повторная отправка')}>
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
