import { useEffect, useMemo, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

type PickerView = 'day' | 'month' | 'year';

const MONTHS_RU_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const MONTHS_RU = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function addMonths(d: Date, delta: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + delta, 1);
}

function addYears(d: Date, delta: number): Date {
  return new Date(d.getFullYear() + delta, d.getMonth(), 1);
}

function formatRuDay(d: Date): string {
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function DateRangePicker({
  value,
  onChange,
  placeholder = 'Период',
  triggerClassName,
  numberOfMonths = 2,
  disabled,
}: {
  value: DateRange | undefined;
  onChange: (next: DateRange | undefined) => void;
  placeholder?: string;
  triggerClassName?: string;
  numberOfMonths?: number;
  disabled?: boolean;
}) {
  const label = useMemo(() => {
    const from = value?.from;
    const to = value?.to;
    if (!from && !to) return placeholder;
    if (from && !to) return formatRuDay(from);
    if (from && to) return `${formatRuDay(from)} — ${formatRuDay(to)}`;
    return placeholder;
  }, [placeholder, value?.from, value?.to]);

  const [open, setOpen] = useState(false);
  const [view, setView] = useState<PickerView>('day');
  const [month, setMonth] = useState<Date>(() => startOfMonth(value?.from || value?.to || new Date()));

  useEffect(() => {
    if (!open) {
      setView('day');
      return;
    }
    const base = value?.from || value?.to;
    if (base) setMonth(startOfMonth(base));
  }, [open, value?.from, value?.to]);

  const activeYear = month.getFullYear();
  const activeMonthIndex = month.getMonth();

  const decadeStart = Math.floor(activeYear / 10) * 10;
  const years = useMemo(() => {
    return Array.from({ length: 12 }).map((_, i) => decadeStart - 1 + i);
  }, [decadeStart]);

  const onPrev = () => {
    if (view === 'day') setMonth((m) => addMonths(m, -1));
    else if (view === 'month') setMonth((m) => addYears(m, -1));
    else setMonth((m) => addYears(m, -10));
  };

  const onNext = () => {
    if (view === 'day') setMonth((m) => addMonths(m, 1));
    else if (view === 'month') setMonth((m) => addYears(m, 1));
    else setMonth((m) => addYears(m, 10));
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn('gap-2 justify-start font-normal', !value?.from && !value?.to && 'text-muted-foreground', triggerClassName)}
        >
          <CalendarIcon className="h-4 w-4" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <div className="flex items-center justify-between gap-1 p-2 border-b border-border">
          <Button type="button" variant="ghost" size="icon" onClick={onPrev}>
            <ChevronLeft className="h-4 w-4" />
          </Button>

          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={cn('px-2', view === 'month' && 'bg-accent')}
              onClick={() => setView('month')}
            >
              {MONTHS_RU[activeMonthIndex]}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={cn('px-2', view === 'year' && 'bg-accent')}
              onClick={() => setView('year')}
            >
              {activeYear}
            </Button>
          </div>

          <Button type="button" variant="ghost" size="icon" onClick={onNext}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {view === 'year' ? (
          <div className="grid grid-cols-4 gap-1 p-2">
            {years.map((y) => {
              const isCurrent = y === activeYear;
              const inDecade = y >= decadeStart && y <= decadeStart + 9;
              return (
                <Button
                  key={y}
                  type="button"
                  variant={isCurrent ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn('h-9', !inDecade && 'text-muted-foreground')}
                  onClick={() => {
                    setMonth(new Date(y, activeMonthIndex, 1));
                    setView('month');
                  }}
                >
                  {y}
                </Button>
              );
            })}
          </div>
        ) : null}

        {view === 'month' ? (
          <div className="grid grid-cols-3 gap-1 p-2">
            {MONTHS_RU_SHORT.map((m, idx) => {
              const isCurrent = idx === activeMonthIndex;
              return (
                <Button
                  key={m}
                  type="button"
                  variant={isCurrent ? 'secondary' : 'ghost'}
                  size="sm"
                  className="h-9"
                  onClick={() => {
                    setMonth(new Date(activeYear, idx, 1));
                    setView('day');
                  }}
                >
                  {m}
                </Button>
              );
            })}
          </div>
        ) : null}

        {view === 'day' ? (
          <Calendar
            mode="range"
            selected={value}
            onSelect={onChange}
            month={month}
            onMonthChange={setMonth}
            numberOfMonths={numberOfMonths}
            initialFocus
            classNames={{
              caption: 'hidden',
              nav: 'hidden',
            }}
          />
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
