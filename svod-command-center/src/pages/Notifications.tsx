import { MainLayout } from '@/components/layout/MainLayout';
import { useApiGet } from '@/hooks/useApiGet';
import { NotificationItem } from '@/components/notifications/NotificationItem';
import { Button } from '@/components/ui/button';
import { Check, Trash2 } from 'lucide-react';
import { toast } from '@/hooks/use-toast';

export default function Notifications() {
  const { data: notifications, refetch } = useApiGet('/notifications', []);
  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <MainLayout 
      title="Уведомления" 
      subtitle={`${unreadCount} непрочитанных`}
    >
      <div className="space-y-4 animate-fade-in">
        {/* Actions bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Всего: <strong className="text-foreground">{notifications.length}</strong></span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => {
                toast({
                  title: 'Уведомления',
                  description: 'В прототипе отмечать прочитанными пока нельзя.',
                });
                refetch();
              }}
            >
              <Check className="h-4 w-4" />
              Прочитать все
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-destructive hover:text-destructive"
              onClick={() =>
                toast({
                  title: 'Очистка',
                  description: 'Очистка уведомлений будет добавлена в следующей версии прототипа.',
                })
              }
            >
              <Trash2 className="h-4 w-4" />
              Очистить
            </Button>
          </div>
        </div>

        {/* Notifications list */}
        <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
          {notifications.map((notification) => (
            <NotificationItem key={notification.id} notification={notification} />
          ))}
        </div>
      </div>
    </MainLayout>
  );
}
