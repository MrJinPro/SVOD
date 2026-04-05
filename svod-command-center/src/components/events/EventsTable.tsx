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
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

interface EventsTableProps {
  events: Event[];
  onViewEvent?: (event: Event) => void;
}

type EventGroup = {
  key: string;
  primary: Event;
  items: Event[];
  isGrouped: boolean;
};

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
  const topScrollRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const ignoreNextScrollRef = useRef({ top: false, bottom: false });
  const [contentWidth, setContentWidth] = useState<number>(0);
  const dragRef = useRef({
    active: false,
    startX: 0,
    startLeft: 0,
    moved: false,
  });
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});

  const getAgencyEventId = (id: string): string | null => {
    const parts = id.split(':');
    if (parts.length >= 3) return parts[parts.length - 1] || null;
    return null;
  };

  const groupedEvents = useMemo<EventGroup[]>(() => {
    const out: EventGroup[] = [];
    const thresholdMs = 1000;

    const sameObject = (a: Event, b: Event) => {
      const aObject = String(a.objectId || a.objectName || '').trim();
      const bObject = String(b.objectId || b.objectName || '').trim();
      return aObject && bObject && aObject === bObject;
    };

    const sameCode = (a: Event, b: Event) => {
      const aCode = String(a.code || '').trim();
      const bCode = String(b.code || '').trim();
      return aCode && bCode && aCode === bCode;
    };

    const fitsFallbackWindow = (a: Event, b: Event) => {
      const ta = new Date(a.timestamp).getTime();
      const tb = new Date(b.timestamp).getTime();
      if (!Number.isFinite(ta) || !Number.isFinite(tb)) return false;
      return Math.abs(ta - tb) <= thresholdMs;
    };

    const canJoinGroup = (event: Event, group: EventGroup) => {
      const primary = group.primary;
      if (event.parentEventId && primary.parentEventId) {
        return event.parentEventId === primary.parentEventId;
      }
      return (
        !event.parentEventId &&
        !primary.parentEventId &&
        event.type === primary.type &&
        sameObject(event, primary) &&
        sameCode(event, primary) &&
        fitsFallbackWindow(event, primary)
      );
    };

    for (const event of events) {
      const currentGroup = out[out.length - 1];
      if (currentGroup && canJoinGroup(event, currentGroup)) {
        currentGroup.items.push(event);
        currentGroup.isGrouped = currentGroup.items.length > 1;
        continue;
      }

      const baseKey = event.parentEventId
        ? `parent:${event.parentEventId}`
        : `fallback:${event.objectId || event.objectName}:${event.code || ''}:${event.timestamp}`;

      out.push({
        key: `${baseKey}:${event.id}`,
        primary: event,
        items: [event],
        isGrouped: false,
      });
    }

    return out;
  }, [events]);

  const isInteractiveTarget = (target: EventTarget | null): boolean => {
    const el = target as Element | null;
    if (!el) return false;
    return Boolean(el.closest('button,a,[role="button"],input,select,textarea'));
  };

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    if (isInteractiveTarget(e.target)) return;

    const node = scrollRef.current;
    if (!node) return;

    dragRef.current.active = true;
    dragRef.current.moved = false;
    dragRef.current.startX = e.clientX;
    dragRef.current.startLeft = node.scrollLeft;

    try {
      node.setPointerCapture(e.pointerId);
    } catch {
      // ignore
    }
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragRef.current.active) return;
    const node = scrollRef.current;
    if (!node) return;

    const delta = e.clientX - dragRef.current.startX;
    if (Math.abs(delta) > 3) dragRef.current.moved = true;
    if (dragRef.current.moved) {
      // Prevent text selection only once the user actually drags.
      e.preventDefault();
    }
    node.scrollLeft = dragRef.current.startLeft - delta;
  };

  const stopDragging = (e?: React.PointerEvent<HTMLDivElement>) => {
    dragRef.current.active = false;
    if (e) {
      const node = scrollRef.current;
      if (node) {
        try {
          node.releasePointerCapture(e.pointerId);
        } catch {
          // ignore
        }
      }
    }
  };

  const onClickCapture = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!dragRef.current.moved) return;
    // If user dragged to scroll, suppress click to avoid accidental actions.
    e.preventDefault();
    e.stopPropagation();
    dragRef.current.moved = false;
  };

  useEffect(() => {
    const updateWidth = () => {
      const bottom = scrollRef.current;
      if (!bottom) return;
      const w = bottom.scrollWidth || 0;
      setContentWidth(w);

      // Keep top scrollbar aligned after width/layout changes.
      const top = topScrollRef.current;
      if (top) top.scrollLeft = bottom.scrollLeft;
    };

    // Next frame to ensure layout is ready.
    const raf = window.requestAnimationFrame(updateWidth);

    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => updateWidth());
      if (scrollRef.current) ro.observe(scrollRef.current);
    }
    window.addEventListener('resize', updateWidth);

    return () => {
      window.cancelAnimationFrame(raf);
      if (ro) ro.disconnect();
      window.removeEventListener('resize', updateWidth);
    };
  }, [events.length]);

  useEffect(() => {
    const top = topScrollRef.current;
    const bottom = scrollRef.current;
    if (!top || !bottom) return;

    // Initial sync.
    top.scrollLeft = bottom.scrollLeft;

    const onTop = () => {
      if (ignoreNextScrollRef.current.top) {
        ignoreNextScrollRef.current.top = false;
        return;
      }
      ignoreNextScrollRef.current.bottom = true;
      bottom.scrollLeft = top.scrollLeft;
    };

    const onBottom = () => {
      if (ignoreNextScrollRef.current.bottom) {
        ignoreNextScrollRef.current.bottom = false;
        return;
      }
      ignoreNextScrollRef.current.top = true;
      top.scrollLeft = bottom.scrollLeft;
    };

    top.addEventListener('scroll', onTop, { passive: true });
    bottom.addEventListener('scroll', onBottom, { passive: true });

    return () => {
      top.removeEventListener('scroll', onTop as any);
      bottom.removeEventListener('scroll', onBottom as any);
    };
  }, []);

  const formatDateTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return {
      date: date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' }),
      time: date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    };
  };

  useEffect(() => {
    setExpandedGroups({});
  }, [events]);

  const renderEventRow = (event: Event, options?: { child?: boolean; group?: EventGroup }) => {
    const { date, time } = formatDateTime(event.timestamp);
    const agencyEventId = getAgencyEventId(event.id);
    const isChild = Boolean(options?.child);
    const group = options?.group;
    const isGroupedRow = Boolean(group?.isGrouped && !isChild);
    const isExpanded = group ? Boolean(expandedGroups[group.key]) : false;

    return (
      <TableRow
        key={event.id}
        title={event.description || ''}
        className={cn(
          'table-row-hover border-border',
          onViewEvent && 'cursor-pointer',
          event.severity === 'critical' && 'bg-severity-critical/5',
          isChild && 'bg-muted/20',
        )}
        role={onViewEvent ? 'button' : undefined}
        tabIndex={onViewEvent ? 0 : undefined}
        onClick={() => onViewEvent?.(event)}
        onKeyDown={(e) => {
          if (!onViewEvent) return;
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onViewEvent(event);
          }
        }}
      >
        <TableCell className="w-[64px] text-center">
          {isGroupedRow ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setExpandedGroups((prev) => ({ ...prev, [group.key]: !prev[group.key] }));
              }}
              title={isExpanded ? 'Скрыть связанные события' : 'Показать связанные события'}
            >
              {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              <span>+{group.items.length - 1}</span>
            </button>
          ) : isChild ? (
            <div className="text-xs text-muted-foreground">↳</div>
          ) : null}
        </TableCell>

        <TableCell className="font-mono text-sm">
          <div className={cn('space-y-0.5', isChild && 'pl-3')}>
            <div className="text-foreground">{time}</div>
            <div className="text-xs text-muted-foreground">{date}</div>
          </div>
        </TableCell>

        <TableCell className="font-mono text-sm text-muted-foreground">
          {agencyEventId || '—'}
        </TableCell>

        <TableCell className="font-mono text-sm text-muted-foreground">
          <div className="space-y-0.5">
            <div>{event.code ? event.code : '—'}</div>
            {isGroupedRow ? (
              <div className="text-[11px] text-muted-foreground">Сгруппировано: {group.items.length}</div>
            ) : null}
          </div>
        </TableCell>
        <TableCell>
          <div className={cn('space-y-0.5', isChild && 'pl-3')}>
            <div className="font-mono text-xs text-muted-foreground">{event.objectId || '—'}</div>
            <div className="font-medium text-foreground">{event.objectName}</div>
            {event.location && (
              <div className="text-xs text-muted-foreground">{event.location}</div>
            )}
          </div>
        </TableCell>
        <TableCell className="max-w-[340px]">
          <div className="text-sm text-foreground truncate" title={event.resultText || ''}>
            {event.resultText || '—'}
          </div>
        </TableCell>
        <TableCell>
          <Badge className={cn('font-medium border', statusStyles[event.status])}>
            {statusLabels[event.status]}
          </Badge>
        </TableCell>
      </TableRow>
    );
  };

  return (
    <div className="rounded-xl border border-border bg-card">
      <div
        ref={topScrollRef}
        className="overflow-x-auto"
      >
        <div className="h-px" style={{ width: contentWidth ? `${contentWidth}px` : undefined }} />
      </div>
      <div
        ref={scrollRef}
        className="overflow-x-auto cursor-grab active:cursor-grabbing"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={stopDragging}
        onPointerCancel={stopDragging}
        onPointerLeave={stopDragging}
        onClickCapture={onClickCapture}
      >
        <Table className="min-w-[960px] whitespace-nowrap">
          <TableHeader>
          <TableRow className="hover:bg-transparent border-border">
            <TableHead className="w-[64px] text-muted-foreground font-medium text-center">+</TableHead>
            <TableHead className="w-[140px] text-muted-foreground font-medium">Время</TableHead>
            <TableHead className="w-[150px] text-muted-foreground font-medium">ID события</TableHead>
            <TableHead className="w-[110px] text-muted-foreground font-medium">Код</TableHead>
            <TableHead className="text-muted-foreground font-medium">№ / Объект / Адрес</TableHead>
            <TableHead className="text-muted-foreground font-medium">Комментарий</TableHead>
            <TableHead className="text-muted-foreground font-medium">Статус</TableHead>
          </TableRow>
          </TableHeader>
          <TableBody>
          {groupedEvents.flatMap((group) => {
            const rows = [renderEventRow(group.primary, { group })];
            if (group.isGrouped && expandedGroups[group.key]) {
              rows.push(...group.items.slice(1).map((item) => renderEventRow(item, { child: true, group })));
            }
            return rows;
          })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
