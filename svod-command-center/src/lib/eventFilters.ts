import type { DateRange } from 'react-day-picker';

type EventFilterMode = {
  search?: string;
  objectId?: string;
  type?: string;
  severity?: string;
  status?: string;
};

export function toLocalIso(dt: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
}

export function setTimeOnDate(d: Date, hhmm: string): Date {
  const [hh, mm] = (hhmm || '00:00').split(':');
  const out = new Date(d);
  out.setHours(Number(hh || '0'), Number(mm || '0'), 0, 0);
  return out;
}

export function hasExplicitEventFilters(
  filters: EventFilterMode & {
    todayOnly?: boolean;
    dateRange?: { from: Date | null; to: Date | null } | DateRange | undefined;
  }
): boolean {
  return Boolean(
    (filters.search || '').trim() ||
      (filters.objectId || '').trim() ||
      filters.todayOnly ||
      filters.dateRange?.from ||
      filters.dateRange?.to ||
      (filters.type && filters.type !== 'all') ||
      (filters.severity && filters.severity !== 'all') ||
      (filters.status && filters.status !== 'all')
  );
}

export function appendEventDateRangeParams(
  params: URLSearchParams,
  opts: {
    todayOnly?: boolean;
    dateRange?: { from: Date | null; to: Date | null } | DateRange | undefined;
    timeFrom?: string;
    timeTo?: string;
  }
) {
  if (opts.todayOnly) {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
    const end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
    params.set('dateFrom', toLocalIso(start));
    params.set('dateTo', toLocalIso(end));
    return;
  }

  const from = opts.dateRange?.from ?? opts.dateRange?.to ?? null;
  const to = opts.dateRange?.to ?? opts.dateRange?.from ?? null;
  if (!from || !to) return;

  const start = opts.timeFrom
    ? setTimeOnDate(from, opts.timeFrom)
    : new Date(from.getFullYear(), from.getMonth(), from.getDate(), 0, 0, 0, 0);
  const end = opts.timeTo
    ? setTimeOnDate(to, opts.timeTo)
    : new Date(to.getFullYear(), to.getMonth(), to.getDate(), 23, 59, 59, 999);

  params.set('dateFrom', toLocalIso(start));
  params.set('dateTo', toLocalIso(end));
}

export function appendCommonEventFilterParams(
  params: URLSearchParams,
  opts: EventFilterMode & {
    includeSystem?: boolean;
    includeCancelled?: boolean;
    includeNoise?: boolean;
    onlyWithOperatorComment?: boolean;
  }
) {
  if (opts.includeSystem) params.set('includeSystem', 'true');
  if (opts.includeCancelled) params.set('includeCancelled', 'true');
  if (opts.includeNoise) params.set('includeNoise', 'true');
  if (opts.onlyWithOperatorComment) params.set('onlyWithOperatorComment', 'true');

  if ((opts.search || '').trim()) params.set('search', opts.search!.trim());
  if ((opts.objectId || '').trim()) params.set('objectId', opts.objectId!.trim());
  if (opts.type && opts.type !== 'all') params.set('type', opts.type);
  if (opts.severity && opts.severity !== 'all') params.set('severity', opts.severity);
  if (opts.status && opts.status !== 'all') params.set('status', opts.status);
}