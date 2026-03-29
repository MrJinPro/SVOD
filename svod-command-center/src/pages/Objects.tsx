import { MainLayout } from '@/components/layout/MainLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useApiGet } from '@/hooks/useApiGet';
import { PaginatedResponse, ObjectListItem } from '@/types';
import { PaginationBar } from '@/components/PaginationBar';
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
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

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
  const [includeDisabled, setIncludeDisabled] = useState(true);
  const [pageNumber, setPageNumber] = useState(1);

  const path = useMemo(() => {
    const params = new URLSearchParams();
    params.set('page', String(pageNumber));
    params.set('pageSize', '50');
    if (search.trim()) params.set('search', search.trim());
    if (includeDisabled) {
      params.set('includeDisabled', 'true');
      params.set('includeIdPrefix', 'true');
      params.set('includeStarPrefix', 'true');
    }
    return `/objects?${params.toString()}`;
  }, [includeDisabled, pageNumber, search]);

  const { data: page, error, isLoading, refetch } = useApiGet<PaginatedResponse<ObjectListItem>>(path, emptyPage);

  return (
    <MainLayout title="Объекты" subtitle="Справочник охраняемых объектов">
      <div className="space-y-4 animate-fade-in">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-muted-foreground">
            Найдено: <strong className="text-foreground">{page.total}</strong>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 mr-2">
              <Checkbox
                id="objects-include-disabled"
                checked={includeDisabled}
                onCheckedChange={(checked) => {
                  setIncludeDisabled(Boolean(checked));
                  setPageNumber(1);
                }}
              />
              <Label htmlFor="objects-include-disabled" className="text-sm whitespace-nowrap">
                Показывать отключённые
              </Label>
            </div>
            <Input
              value={draftSearch}
              onChange={(e) => setDraftSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setSearch(draftSearch);
                  setPageNumber(1);
                }
              }}
              placeholder="Поиск (номер, имя, адрес, клиент, ответственный, телефон)…"
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

        <PaginationBar
          isLoading={isLoading}
          shown={page.data.length}
          total={page.total}
          page={pageNumber}
          totalPages={page.totalPages}
          onPageChange={(next) => setPageNumber(next)}
        />

        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-border">
                <TableHead className="w-[120px] text-muted-foreground font-medium">ID</TableHead>
                <TableHead className="text-muted-foreground font-medium">Название</TableHead>
                <TableHead className="text-muted-foreground font-medium">Адрес</TableHead>
                <TableHead className="text-muted-foreground font-medium">Клиент</TableHead>
                <TableHead className="w-[120px] text-muted-foreground font-medium">Статус</TableHead>
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
                  <TableCell className={o.disabled ? 'text-destructive font-medium' : 'text-foreground'}>
                    {o.disabled ? 'Отключён' : 'Активен'}
                  </TableCell>
                  <TableCell className="text-foreground">
                    {typeof o.eventsToday === 'number' ? o.eventsToday : '—'}
                  </TableCell>
                </TableRow>
              ))}
              {!isLoading && page.data.length === 0 && (
                <TableRow className="border-border">
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-10">
                    Ничего не найдено
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        <PaginationBar
          isLoading={isLoading}
          shown={page.data.length}
          total={page.total}
          page={pageNumber}
          totalPages={page.totalPages}
          onPageChange={(next) => setPageNumber(next)}
        />
      </div>
    </MainLayout>
  );
}
