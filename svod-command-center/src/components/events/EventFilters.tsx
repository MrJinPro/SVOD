import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Calendar, Filter, RotateCcw, Search } from 'lucide-react';

export type EventFiltersValue = {
  search: string;
  type: string;
  severity: string;
  status: string;
  todayOnly: boolean;
};

interface EventFiltersProps {
  value: EventFiltersValue;
  onChange: (next: EventFiltersValue) => void;
  onApply: () => void;
  onReset: () => void;
}

export function EventFilters({ value, onChange, onApply, onReset }: EventFiltersProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[250px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Поиск по событиям..."
            className="pl-9 bg-background"
            value={value.search}
            onChange={(e) => onChange({ ...value, search: e.target.value })}
          />
        </div>

        {/* Date range */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => onChange({ ...value, todayOnly: !value.todayOnly })}
          >
            <Calendar className="h-4 w-4" />
            Сегодня
          </Button>
        </div>

        {/* Type filter */}
        <Select value={value.type} onValueChange={(v) => onChange({ ...value, type: v })}>
          <SelectTrigger className="w-[160px] bg-background">
            <SelectValue placeholder="Тип события" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все типы</SelectItem>
            <SelectItem value="intrusion">Проникновение</SelectItem>
            <SelectItem value="alarm">Тревога</SelectItem>
            <SelectItem value="access">Доступ</SelectItem>
            <SelectItem value="patrol">Обход</SelectItem>
            <SelectItem value="incident">Инцидент</SelectItem>
            <SelectItem value="maintenance">ТО</SelectItem>
          </SelectContent>
        </Select>

        {/* Severity filter */}
        <Select value={value.severity} onValueChange={(v) => onChange({ ...value, severity: v })}>
          <SelectTrigger className="w-[160px] bg-background">
            <SelectValue placeholder="Серьёзность" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все уровни</SelectItem>
            <SelectItem value="critical">Критический</SelectItem>
            <SelectItem value="warning">Внимание</SelectItem>
            <SelectItem value="info">Информация</SelectItem>
            <SelectItem value="success">Норма</SelectItem>
          </SelectContent>
        </Select>

        {/* Status filter */}
        <Select value={value.status} onValueChange={(v) => onChange({ ...value, status: v })}>
          <SelectTrigger className="w-[160px] bg-background">
            <SelectValue placeholder="Статус" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все статусы</SelectItem>
            <SelectItem value="active">Активно</SelectItem>
            <SelectItem value="pending">В обработке</SelectItem>
            <SelectItem value="resolved">Завершено</SelectItem>
          </SelectContent>
        </Select>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" className="gap-2" onClick={onApply}>
            <Filter className="h-4 w-4" />
            Применить
          </Button>
          <Button variant="ghost" size="sm" className="gap-2" onClick={onReset}>
            <RotateCcw className="h-4 w-4" />
            Сбросить
          </Button>
        </div>
      </div>
    </div>
  );
}
