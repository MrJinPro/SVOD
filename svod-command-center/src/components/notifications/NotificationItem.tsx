import { Notification, EventSeverity } from '@/types';
import { cn } from '@/lib/utils';
import { AlertTriangle, Bell, CheckCircle, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';

interface NotificationItemProps {
  notification: Notification;
}

const severityIcons: Record<EventSeverity, React.ElementType> = {
  critical: AlertTriangle,
  warning: AlertTriangle,
  info: Info,
  success: CheckCircle,
};

const severityStyles: Record<EventSeverity, string> = {
  critical: 'text-severity-critical bg-severity-critical/10',
  warning: 'text-severity-warning bg-severity-warning/10',
  info: 'text-severity-info bg-severity-info/10',
  success: 'text-severity-success bg-severity-success/10',
};

export function NotificationItem({ notification }: NotificationItemProps) {
  const Icon = severityIcons[notification.severity];

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 60) {
      return `${diffMins} мин. назад`;
    } else if (diffHours < 24) {
      return `${diffHours} ч. назад`;
    } else {
      return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    }
  };

  return (
    <div
      className={cn(
        'flex items-start gap-4 p-4 transition-colors',
        !notification.read && 'bg-accent/30',
        'hover:bg-accent/50'
      )}
    >
      <div className={cn('rounded-full p-2', severityStyles[notification.severity])}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h4 className={cn('text-sm font-medium', !notification.read && 'text-foreground')}>
              {notification.title}
            </h4>
            <p className="text-sm text-muted-foreground mt-0.5">{notification.message}</p>
          </div>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {formatTime(notification.timestamp)}
          </span>
        </div>
        {notification.eventId && (
          <Button asChild variant="link" size="sm" className="h-auto p-0 mt-2 text-primary">
            <Link to="/events">Перейти к событию →</Link>
          </Button>
        )}
      </div>
      {!notification.read && (
        <div className="h-2 w-2 rounded-full bg-primary mt-2 flex-shrink-0" />
      )}
    </div>
  );
}
