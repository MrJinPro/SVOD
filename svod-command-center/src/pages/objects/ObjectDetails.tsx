import { MainLayout } from '@/components/layout/MainLayout';
import { useApiGet } from '@/hooks/useApiGet';
import { apiGet } from '@/lib/api';
import { Event, ObjectDetails as ObjectDetailsType, PaginatedResponse } from '@/types';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Separator } from '@/components/ui/separator';
import { EventsTable } from '@/components/events/EventsTable';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const emptyObject: ObjectDetailsType = {
  id: '',
  name: '',
  disabled: false,
  groups: [],
  responsibles: [],
};

const emptyEvents: PaginatedResponse<Event> = {
  data: [],
  total: 0,
  page: 1,
  pageSize: 50,
  totalPages: 1,
};

export default function ObjectDetails() {
  const { objectId } = useParams();
  const [eventsPage, setEventsPage] = useState(1);

  const id = objectId ? decodeURIComponent(objectId) : '';

  const { data: obj, error, isLoading, refetch } = useApiGet<ObjectDetailsType>(
    `/objects/${encodeURIComponent(id)}`,
    emptyObject
  );

  const eventsPath = useMemo(() => {
    const params = new URLSearchParams();
    params.set('page', String(eventsPage));
    params.set('pageSize', '50');
    return `/objects/${encodeURIComponent(id)}/events?${params.toString()}`;
  }, [id, eventsPage]);

  const { data: eventsPageData, error: eventsError, isLoading: eventsLoading } = useApiGet<PaginatedResponse<Event>>(
    eventsPath,
    emptyEvents
  );

  const title = obj?.name || id || 'Объект';

  return (
    <MainLayout title={title} subtitle={obj?.address || 'Карточка объекта'}>
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            ID: <span className="font-mono text-foreground">{id}</span>
          </div>
          <Button variant="outline" onClick={refetch} disabled={isLoading}>
            Обновить
          </Button>
        </div>

        {error && <div className="text-sm text-destructive">Ошибка загрузки: {String(error)}</div>}

        <div className="rounded-xl border border-border bg-card p-6">
          <div className="text-sm text-muted-foreground">Клиент</div>
          <div className="text-foreground font-medium">{obj?.clientName || '—'}</div>
          <Separator className="my-4" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground">Адрес</div>
              <div className="text-foreground">{obj?.address || '—'}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Статус</div>
              <div className="text-foreground">{obj?.disabled ? 'Отключен' : 'Активен'}</div>
            </div>
          </div>
          {obj?.remarks && (
            <>
              <Separator className="my-4" />
              <div className="text-muted-foreground text-sm">Примечание</div>
              <div className="text-foreground text-sm whitespace-pre-wrap">{obj.remarks}</div>
            </>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="text-lg font-semibold text-foreground">Группы</h3>
          <Separator className="my-4" />
          {obj?.groups?.length ? (
            <div className="rounded-lg border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent border-border">
                    <TableHead className="w-[90px] text-muted-foreground font-medium">Группа</TableHead>
                    <TableHead className="text-muted-foreground font-medium">Название</TableHead>
                    <TableHead className="w-[120px] text-muted-foreground font-medium">Состояние</TableHead>
                    <TableHead className="w-[170px] text-muted-foreground font-medium">Время</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {obj.groups.map((g) => (
                    <TableRow key={String(g.group)} className="border-border">
                      <TableCell className="font-mono text-sm text-foreground">{g.group}</TableCell>
                      <TableCell className="text-foreground">{g.name || '—'}</TableCell>
                      <TableCell className="text-foreground">{g.isOpen ? 'Открыта' : 'Закрыта'}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {g.timeEvent ? new Date(g.timeEvent).toLocaleString('ru-RU') : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">Нет данных</div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="text-lg font-semibold text-foreground">Ответственные</h3>
          <Separator className="my-4" />
          {obj?.responsibles?.length ? (
            <>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent border-border">
                      <TableHead className="w-[90px] text-muted-foreground font-medium">Группа</TableHead>
                      <TableHead className="w-[90px] text-muted-foreground font-medium">Очередь</TableHead>
                      <TableHead className="text-muted-foreground font-medium">ФИО</TableHead>
                      <TableHead className="text-muted-foreground font-medium">Адрес</TableHead>
                      <TableHead className="w-[260px] text-muted-foreground font-medium">Телефоны</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {obj.responsibles.slice(0, 100).map((r) => (
                      <TableRow key={r.id} className="border-border">
                        <TableCell className="text-foreground">
                          {typeof r.group === 'number' ? <span className="font-mono">{r.group}</span> : '—'}
                        </TableCell>
                        <TableCell className="text-foreground">
                          {typeof r.order === 'number' ? <span className="font-mono">{r.order}</span> : '—'}
                        </TableCell>
                        <TableCell className="text-foreground font-medium">{r.name || '—'}</TableCell>
                        <TableCell className="text-muted-foreground">{r.address || '—'}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {r.phones?.length ? r.phones.join(', ') : '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              {obj.responsibles.length > 100 && (
                <div className="text-xs text-muted-foreground mt-2">Показаны первые 100 записей</div>
              )}
            </>
          ) : (
            <div className="text-sm text-muted-foreground">Нет данных</div>
          )}
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-lg font-semibold text-foreground">События объекта</div>
            <div className="text-sm text-muted-foreground">
              {eventsLoading ? 'Загрузка…' : `Всего: ${eventsPageData.total}`}
            </div>
          </div>

          {eventsError && <div className="text-sm text-destructive">Ошибка загрузки событий: {String(eventsError)}</div>}

          <EventsTable events={eventsPageData.data} />

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {eventsLoading ? 'Загрузка…' : `Показано ${eventsPageData.data.length} из ${eventsPageData.total}`}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={eventsPage <= 1}
                onClick={() => setEventsPage((p) => Math.max(1, p - 1))}
              >
                Назад
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={eventsPage >= eventsPageData.totalPages}
                onClick={() => setEventsPage((p) => Math.min(eventsPageData.totalPages, p + 1))}
              >
                Вперёд
              </Button>
            </div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
