import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

type Props = {
  isLoading: boolean;
  shown: number;
  total: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
};

export function PaginationBar({
  isLoading,
  shown,
  total,
  page,
  totalPages,
  onPageChange,
}: Props) {
  const safeTotalPages = Math.max(1, Number.isFinite(totalPages) ? totalPages : 1);
  const safePage = Math.min(Math.max(1, page), safeTotalPages);

  const canGoPrev = safePage > 1;
  const canGoNext = safePage < safeTotalPages;

  return (
    <div className="flex items-center justify-between text-sm text-muted-foreground">
      <span>{isLoading ? 'Загрузка…' : `Показано ${shown} из ${total}`}</span>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={!canGoPrev}
          onClick={() => onPageChange(1)}
          title="В начало"
        >
          <ChevronsLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!canGoPrev}
          onClick={() => onPageChange(safePage - 1)}
        >
          <ChevronLeft className="h-4 w-4" />
          Назад
        </Button>
        <span className="tabular-nums">
          {safePage} / {safeTotalPages}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={!canGoNext}
          onClick={() => onPageChange(safePage + 1)}
        >
          Вперёд
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!canGoNext}
          onClick={() => onPageChange(safeTotalPages)}
          title="В конец"
        >
          <ChevronsRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
