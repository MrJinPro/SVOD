import { Event, EventSeverity, EventStatus, EventType } from '@/types';
import { cn } from '@/lib/utils';
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
import { Eye, MoreHorizontal } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface EventsTableProps {
  events: Event[];
  onViewEvent?: (event: Event) => void;
}

const severityLabels: Record<EventSeverity, string> = {
  critical: 'Критический',
  warning: 'Внимание',
  info: 'Информация',
  success: 'Норма',
};

const statusLabels: Record<EventStatus, string> = {
  active: 'Активно',
  pending: 'В обработке',
  resolved: 'Завершено',
};

const typeLabels: Record<EventType, string> = {
  intrusion: 'Проникновение',
  alarm: 'Тревога',
  access: 'Доступ',
  patrol: 'Обход',
  incident: 'Инцидент',
  maintenance: 'ТО',
};

const severityStyles: Record<EventSeverity, string> = {
  critical: 'badge-critical',
  warning: 'badge-warning',
  info: 'badge-info',
  success: 'badge-success',
};

const statusStyles: Record<EventStatus, string> = {
  active: 'bg-status-active/10 text-status-active border-status-active/30',
  pending: 'bg-status-pending/10 text-status-pending border-status-pending/30',
  resolved: 'bg-muted text-muted-foreground border-muted',
};

export function EventsTable({ events, onViewEvent }: EventsTableProps) {
  const formatDateTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return {
      date: date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' }),
      time: date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    };
  };

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent border-border">
            <TableHead className="w-[140px] text-muted-foreground font-medium">Время</TableHead>
            <TableHead className="text-muted-foreground font-medium">Тип</TableHead>
            <TableHead className="text-muted-foreground font-medium">Код / сообщение</TableHead>
            <TableHead className="text-muted-foreground font-medium">Объект</TableHead>
            <TableHead className="text-muted-foreground font-medium">Клиент</TableHead>
            <TableHead className="text-muted-foreground font-medium">Серьёзность</TableHead>
            <TableHead className="text-muted-foreground font-medium">Статус</TableHead>
            <TableHead className="text-muted-foreground font-medium">Статус агентства</TableHead>
            <TableHead className="text-muted-foreground font-medium">Оператор</TableHead>
            <TableHead className="w-[80px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {events.map((event) => {
            const { date, time } = formatDateTime(event.timestamp);
            return (
              <TableRow 
                key={event.id} 
                title={event.description || ''}
                className={cn(
                  'table-row-hover border-border',
                  event.severity === 'critical' && 'bg-severity-critical/5'
                )}
              >
                <TableCell className="font-mono text-sm">
                  <div className="space-y-0.5">
                    <div className="text-foreground">{time}</div>
                    <div className="text-xs text-muted-foreground">{date}</div>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="space-y-1">
                    <Badge variant="outline" className="font-medium">
                      {typeLabels[event.type]}
                    </Badge>
                  </div>
                </TableCell>

                <TableCell className="max-w-[420px]">
                  <div className="space-y-0.5">
                    <div className="font-mono text-xs text-muted-foreground">
                      {event.code ? event.code : '—'}
                    </div>
                    <div
                      className="text-sm text-foreground truncate"
                      title={event.codeText || event.description || ''}
                    >
                      {event.codeText || '—'}
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="space-y-0.5">
                    <div className="font-medium text-foreground">{event.objectName}</div>
                    {event.location && (
                      <div className="text-xs text-muted-foreground">{event.location}</div>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-foreground">{event.clientName}</TableCell>
                <TableCell>
                  <Badge className={cn('font-medium border', severityStyles[event.severity])}>
                    {severityLabels[event.severity]}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge className={cn('font-medium border', statusStyles[event.status])}>
                    {statusLabels[event.status]}
                  </Badge>
                </TableCell>

                <TableCell className="text-muted-foreground">
                  {event.stateName || '—'}
                </TableCell>

                <TableCell className="text-muted-foreground">
                  {event.operatorId || '—'}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-8 w-8"
                      onClick={() => onViewEvent?.(event)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem>Просмотреть детали</DropdownMenuItem>
                        <DropdownMenuItem>Изменить статус</DropdownMenuItem>
                        <DropdownMenuItem>Назначить оператора</DropdownMenuItem>
                        <DropdownMenuItem>Экспортировать</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
