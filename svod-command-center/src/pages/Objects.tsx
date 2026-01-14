import { MainLayout } from '@/components/layout/MainLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useApiGet } from '@/hooks/useApiGet';
import { PaginatedResponse, ObjectListItem } from '@/types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const emptyPage: PaginatedResponse<ObjectListItem> = {
  data: [],
  total: 0,
  page: 1,
  pageSize: 50,
  totalPages: 1,
};

export default function Objects() {
  const navigate = useNavigate();
  const [draftSearch, setDraftSearch] = useState('');
  const [search, setSearch] = useState('');
  const [pageNumber, setPageNumber] = useState(1);

  const path = useMemo(() => {
    const params = new URLSearchParams();
    params.set('page', String(pageNumber));
    params.set('pageSize', '50');
    if (search.trim()) params.set('search', search.trim());
    return `/objects?${params.toString()}`;
  }, [pageNumber, search]);

  const { data: page, error, isLoading, refetch } = useApiGet<PaginatedResponse<ObjectListItem>>(path, emptyPage);

  return (
    <MainLayout title="Объекты" subtitle="Справочник охраняемых объектов">
      <div className="space-y-4 animate-fade-in">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-muted-foreground">
            Найдено: <strong className="text-foreground">{page.total}</strong>
          </div>
          <div className="flex items-center gap-2">
            <Input
              value={draftSearch}
              onChange={(e) => setDraftSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setSearch(draftSearch);
                  setPageNumber(1);
                }
              }}
              placeholder="Поиск (номер, имя, адрес, клиент)…"
              className="w-80"
            />
            <Button
              variant="outline"
              onClick={() => {
                setSearch(draftSearch);
                setPageNumber(1);
              }}
            >
              Найти
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setDraftSearch('');
                setSearch('');
                setPageNumber(1);
              }}
            >
              Сброс
            </Button>
            <Button variant="outline" onClick={refetch}>
              Обновить
            </Button>
          </div>
        </div>

        {error && <div className="text-sm text-destructive">Ошибка загрузки: {String(error)}</div>}

        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-border">
                <TableHead className="w-[120px] text-muted-foreground font-medium">ID</TableHead>
                <TableHead className="text-muted-foreground font-medium">Название</TableHead>
                <TableHead className="text-muted-foreground font-medium">Адрес</TableHead>
                <TableHead className="text-muted-foreground font-medium">Клиент</TableHead>
                <TableHead className="w-[110px] text-muted-foreground font-medium">Сегодня</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.data.map((o) => (
                <TableRow
                  key={o.id}
                  className="table-row-hover border-border cursor-pointer"
                  onClick={() => navigate(`/objects/${encodeURIComponent(o.id)}`)}
                  title={o.address || ''}
                >
                  <TableCell className="font-mono text-sm">{o.id}</TableCell>
                  <TableCell className="font-medium text-foreground">{o.name || o.id}</TableCell>
                  <TableCell className="text-muted-foreground">{o.address || '—'}</TableCell>
                  <TableCell className="text-foreground">{o.clientName || '—'}</TableCell>
                  <TableCell className="text-foreground">
                    {typeof o.eventsToday === 'number' ? o.eventsToday : '—'}
                  </TableCell>
                </TableRow>
              ))}
              {!isLoading && page.data.length === 0 && (
                <TableRow className="border-border">
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-10">
                    Ничего не найдено
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{isLoading ? 'Загрузка…' : `Показано ${page.data.length} из ${page.total}`}</span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pageNumber <= 1}
              onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            >
              Назад
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pageNumber >= page.totalPages}
              onClick={() => setPageNumber((p) => Math.min(page.totalPages, p + 1))}
            >
              Вперёд
            </Button>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
