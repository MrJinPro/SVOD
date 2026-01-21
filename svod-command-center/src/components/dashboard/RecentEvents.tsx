import { EventSeverity, EventStatus } from '@/types';
import { cn } from '@/lib/utils';
import { Clock, MapPin, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { useApiGet } from '@/hooks/useApiGet';

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

const severityStyles: Record<EventSeverity, string> = {
  critical: 'badge-critical',
  warning: 'badge-warning',
  info: 'badge-info',
  success: 'badge-success',
};

export function RecentEvents() {
  const { data: page } = useApiGet(
    '/events?page=1&pageSize=5',
    { data: [], total: 0, page: 1, pageSize: 5, totalPages: 1 }
  );
  const recentEvents = page.data;

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between p-6 border-b border-border">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Последние события</h3>
          <p className="text-sm text-muted-foreground">Обновлено только что</p>
        </div>
        <Link to="/events">
          <Button variant="ghost" size="sm" className="gap-1">
            Все события
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
      
      <div className="divide-y divide-border">
        {recentEvents.map((event) => (
          <div key={event.id} className="p-4 hover:bg-accent/50 transition-colors cursor-pointer">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={cn('px-2 py-0.5 rounded text-xs font-medium', severityStyles[event.severity])}>
                    {severityLabels[event.severity]}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {statusLabels[event.status]}
                  </span>
                </div>
                <p className="text-sm font-medium text-foreground truncate">
                  {(event.codeText || event.description) || '—'}
                </p>
                <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatTime(event.timestamp)}
                  </span>
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {event.objectName}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">{event.clientName}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
