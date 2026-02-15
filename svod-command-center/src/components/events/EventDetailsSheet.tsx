import { useEffect, useMemo, useState } from 'react';

import type { Event, EventAction, EventDetailsResponse } from '@/types';
import { apiGet } from '@/lib/api';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  event: Event | null;
}

export function EventDetailsSheet({ open, onOpenChange, event }: Props) {
  const [details, setDetails] = useState<EventDetailsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const eventId = event?.id ?? null;

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!open || !eventId) return;
      try {
        setLoading(true);
        setError(null);
        const res = await apiGet<EventDetailsResponse>(`/events/${encodeURIComponent(eventId)}?actionsLimit=500`);
        if (!cancelled) setDetails(res);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Ошибка загрузки деталей');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [open, eventId]);

  const fmtTs = (ts: string) => {
    const d = new Date(ts);
    const date = d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const time = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    return `${date} ${time}`;
  };

  const actions: EventAction[] = details?.actions ?? [];
  const header = useMemo(() => {
    if (!event) return 'Событие';
    return event.objectName ? `Событие — ${event.objectName}` : 'Событие';
  }, [event]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[520px] sm:w-[640px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{header}</SheetTitle>
        </SheetHeader>

        {!event && (
          <div className="mt-4 text-sm text-muted-foreground">Событие не выбрано</div>
        )}

        {event && (
          <div className="mt-4 space-y-3">
            <div className="text-sm text-muted-foreground">ID: <span className="text-foreground font-mono">{event.id}</span></div>
            <div className="text-sm">Время: <span className="text-foreground">{fmtTs(event.timestamp)}</span></div>
            <div className="text-sm">Клиент: <span className="text-foreground">{event.clientName}</span></div>
            <div className="text-sm">Объект: <span className="text-foreground">{event.objectName}</span></div>
            {event.location && (
              <div className="text-sm">Адрес: <span className="text-foreground">{event.location}</span></div>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant="outline">{event.type}</Badge>
              <Badge
                className={cn(
                  'border',
                  event.status === 'active' && 'bg-status-active/10 text-status-active border-status-active/30',
                  event.status === 'pending' && 'bg-status-pending/10 text-status-pending border-status-pending/30',
                  event.status === 'resolved' && 'bg-muted text-muted-foreground border-muted',
                )}
              >
                {event.status}
              </Badge>
              <Badge
                className={cn(
                  'border',
                  event.severity === 'critical' && 'badge-critical',
                  event.severity === 'warning' && 'badge-warning',
                  event.severity === 'info' && 'badge-info',
                  event.severity === 'success' && 'badge-success',
                )}
              >
                {event.severity}
              </Badge>
              {event.code && (
                <Badge variant="outline" className="font-mono">{event.code}</Badge>
              )}
              {event.stateName && (
                <Badge variant="outline">{event.stateName}</Badge>
              )}
            </div>

            {event.description && (
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs text-muted-foreground mb-1">Описание</div>
                <div className="text-sm whitespace-pre-wrap">{event.description}</div>
              </div>
            )}
          </div>
        )}

        <div className="mt-6">
          <div className="text-sm font-medium">Действия (eventservice)</div>
          {loading && <div className="mt-2 text-sm text-muted-foreground">Загрузка…</div>}
          {error && <div className="mt-2 text-sm text-destructive">{error}</div>}
          {!loading && !error && actions.length === 0 && (
            <div className="mt-2 text-sm text-muted-foreground">Нет действий по этому событию</div>
          )}
          {!loading && !error && actions.length > 0 && (
            <div className="mt-2 space-y-2">
              {actions.map((a, idx) => (
                <div key={`${a.actionTime}-${idx}`} className="rounded-md border border-border p-2">
                  <div className="text-sm text-foreground">{a.actionName}</div>
                  <div className="text-xs text-muted-foreground">
                    {a.actionTime ? fmtTs(a.actionTime) : '—'}
                    {a.operatorName ? ` • ${a.operatorName}` : ''}
                    {a.gbrName ? ` • ${a.gbrName}` : ''}
                    {a.computer ? ` • ${a.computer}` : ''}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}