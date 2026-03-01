import { useEffect, useMemo, useState } from 'react';

import type { Event, EventAction, EventDetailsResponse } from '@/types';
import { apiGet } from '@/lib/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const severityLabels: Record<string, string> = {
  critical: 'Критический',
  warning: 'Внимание',
  info: 'Информация',
  success: 'Норма',
};

const statusLabels: Record<string, string> = {
  active: 'Активно',
  pending: 'В обработке',
  resolved: 'Завершено',
};

const typeLabels: Record<string, string> = {
  intrusion: 'Проникновение',
  alarm: 'Тревога',
  access: 'Доступ',
  patrol: 'Обход',
  incident: 'Инцидент',
  maintenance: 'ТО',
};

function normalizeEnum(value: unknown): string {
  const s = String(value ?? '').trim();
  if (!s) return '';
  return s.split('.', 1)[0] || s;
}

function getAgencyEventId(id: string): string | null {
  const parts = String(id || '').split(':');
  if (parts.length >= 3) return parts[parts.length - 1] || null;
  return null;
}

function humanizeDescription(text: string): string {
  if (!text) return text;
  const map: Array<[RegExp, string]> = [
    [/^\s*Event_id\s*:/i, 'ID события:'],
    [/^\s*Panel_id\s*:/i, '№ объекта:'],
    [/^\s*Date_Key\s*:/i, 'Дата (ключ):'],
  ];
  return text
    .split(/\r?\n/)
    .map((line) => {
      let out = line;
      for (const [re, repl] of map) out = out.replace(re, repl);
      return out;
    })
    .join('\n');
}

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
        const res = await apiGet<EventDetailsResponse>(
          `/events/details?eventId=${encodeURIComponent(eventId)}&actionsLimit=500`
        );
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

  const fmtOptional = (value: string | null | undefined) => {
    const v = String(value ?? '').trim();
    return v ? v : '—';
  };

  const actions: EventAction[] = details?.actions ?? [];
  const header = useMemo(() => {
    if (!event) return 'Событие';
    return event.objectName ? `Событие — ${event.objectName}` : 'Событие';
  }, [event]);

  const typeKey = normalizeEnum(event?.type);
  const statusKey = normalizeEnum(event?.status);
  const severityKey = normalizeEnum(event?.severity);
  const typeLabel = typeLabels[typeKey] || (typeKey ? typeKey : '—');
  const statusLabel = statusLabels[statusKey] || (statusKey ? statusKey : '—');
  const severityLabel = severityLabels[severityKey] || (severityKey ? severityKey : '—');
  const agencyEventId = event?.id ? getAgencyEventId(event.id) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{header}</DialogTitle>
        </DialogHeader>

        {!event && (
          <div className="mt-4 text-sm text-muted-foreground">Событие не выбрано</div>
        )}

        {event && (
          <div className="mt-4 space-y-3">
            <div className="text-sm text-muted-foreground">
              ID события:{' '}
              <span className="text-foreground font-mono">{agencyEventId || event.id}</span>
            </div>
            <div className="text-sm">Время: <span className="text-foreground">{fmtTs(event.timestamp)}</span></div>
            <div className="text-sm">Клиент: <span className="text-foreground">{event.clientName}</span></div>
            <div className="text-sm">Объект: <span className="text-foreground">{event.objectName}</span></div>
            {event.location && (
              <div className="text-sm">Адрес: <span className="text-foreground">{event.location}</span></div>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant="outline">{typeLabel}</Badge>
              <Badge
                className={cn(
                  'border',
                  statusKey === 'active' && 'bg-status-active/10 text-status-active border-status-active/30',
                  statusKey === 'pending' && 'bg-status-pending/10 text-status-pending border-status-pending/30',
                  statusKey === 'resolved' && 'bg-muted text-muted-foreground border-muted',
                )}
              >
                {statusLabel}
              </Badge>
              <Badge
                className={cn(
                  'border',
                  severityKey === 'critical' && 'badge-critical',
                  severityKey === 'warning' && 'badge-warning',
                  severityKey === 'info' && 'badge-info',
                  severityKey === 'success' && 'badge-success',
                )}
              >
                {severityLabel}
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
                <div className="text-sm whitespace-pre-wrap">{humanizeDescription(event.description)}</div>
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
                  <div className="flex items-start justify-between gap-3">
                    <div className="text-sm font-medium text-foreground leading-snug">{a.actionName}</div>
                    <div className="text-xs text-muted-foreground whitespace-nowrap">
                      {a.actionTime ? fmtTs(a.actionTime) : '—'}
                    </div>
                  </div>

                  <div className="mt-1 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    <div className="text-muted-foreground">
                      Оператор: <span className="text-foreground">{fmtOptional(a.operatorName)}</span>
                    </div>
                    <div className="text-muted-foreground">
                      ПК: <span className="text-foreground">{fmtOptional(a.computer)}</span>
                    </div>
                    <div className="text-muted-foreground sm:col-span-2">
                      ГБР: <span className="text-foreground">{fmtOptional(a.gbrName)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}