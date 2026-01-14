import { MainLayout } from '@/components/layout/MainLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { apiGet, apiPost } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import { Database, RefreshCw } from 'lucide-react';
import { useState } from 'react';

type SyncResult = Record<string, any>;

type JobInfo = {
  id: string;
  type: string;
  status: 'queued' | 'running' | 'done' | 'error';
  result?: any;
  error?: string;
};

export default function Integration() {
  const [isSyncingObjects, setIsSyncingObjects] = useState(false);
  const [isSyncingEvents, setIsSyncingEvents] = useState(false);
  const [eventsLimit, setEventsLimit] = useState('500');
  const [lastResult, setLastResult] = useState<SyncResult | null>(null);

  const pollJobUntilDone = async (jobId: string, timeoutMs = 30 * 60 * 1000) => {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      const job = await apiGet<JobInfo>(`/db/jobs/${encodeURIComponent(jobId)}`);
      if (job.status === 'done') return job;
      if (job.status === 'error') return job;
      await new Promise((r) => setTimeout(r, 1500));
    }
    throw new Error('Таймаут ожидания завершения синхронизации');
  };

  const syncObjects = async () => {
    setIsSyncingObjects(true);
    try {
      // Prefer background sync to avoid long-running HTTP request.
      let accepted: any = null;
      try {
        accepted = await apiPost<{ status: string; jobId: string }>('/db/sync/objects/start');
      } catch {
        accepted = null;
      }

      if (accepted?.jobId) {
        toast({
          title: 'Синхронизация объектов',
          description: 'Запущено в фоне — можно продолжать работу.',
        });
        const job = await pollJobUntilDone(accepted.jobId);
        const res = job.result as SyncResult | undefined;
        if (job.status === 'error') {
          throw new Error(job.error || 'Ошибка синхронизации');
        }
        setLastResult(res ?? job);
        toast({
          title: 'Синхронизация объектов',
          description: `Готово: ${res?.objects ?? 0} объектов`,
        });
      } else {
        // Fallback to old endpoint.
        const res = await apiPost<SyncResult>('/db/sync/objects');
        setLastResult(res);
        toast({
          title: 'Синхронизация объектов',
          description: `Готово: ${res?.objects ?? 0} объектов`,
        });
      }
    } catch (e: any) {
      toast({
        title: 'Ошибка синхронизации объектов',
        description: e?.message || 'Ошибка запроса',
        variant: 'destructive',
      });
    } finally {
      setIsSyncingObjects(false);
    }
  };

  const syncEvents = async () => {
    const limit = Math.max(1, Math.min(5000, Number(eventsLimit) || 500));
    setIsSyncingEvents(true);
    try {
      const res = await apiPost<SyncResult>(`/db/sync/events?limit=${encodeURIComponent(String(limit))}`);
      setLastResult(res);
      toast({
        title: 'Синхронизация событий',
        description: `Готово: ${res?.processed ?? 0} событий`,
      });
    } catch (e: any) {
      toast({
        title: 'Ошибка синхронизации событий',
        description: e?.message || 'Ошибка запроса',
        variant: 'destructive',
      });
    } finally {
      setIsSyncingEvents(false);
    }
  };

  return (
    <MainLayout title="Интеграция" subtitle="Загрузка реальных данных из агентской БД">
      <div className="max-w-3xl space-y-6 animate-fade-in">
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-lg bg-severity-info/10 p-2">
              <Database className="h-5 w-5 text-severity-info" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Справочники</h3>
              <p className="text-sm text-muted-foreground">Объекты, группы, ответственные, телефоны</p>
            </div>
          </div>
          <Separator className="mb-4" />
          <div className="flex items-center justify-between gap-4">
            <div className="text-sm text-muted-foreground">
              Запускает синхронизацию из MSSQL таблиц `Panel/Groups/Responsibles*`.
            </div>
            <Button className="gap-2" onClick={syncObjects} disabled={isSyncingObjects}>
              <RefreshCw className={isSyncingObjects ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
              Синхронизировать объекты
            </Button>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-lg bg-severity-warning/10 p-2">
              <Database className="h-5 w-5 text-severity-warning" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">События</h3>
              <p className="text-sm text-muted-foreground">Архивные таблицы `archiveYYYYMM01/eventserviceYYYYMM01`</p>
            </div>
          </div>
          <Separator className="mb-4" />

          <div className="flex items-end justify-between gap-4">
            <div className="grid gap-2">
              <Label htmlFor="events-limit">Лимит (1–5000)</Label>
              <Input
                id="events-limit"
                value={eventsLimit}
                onChange={(e) => setEventsLimit(e.target.value)}
                type="number"
                className="w-32"
                min={1}
                max={5000}
              />
            </div>

            <Button className="gap-2" onClick={syncEvents} disabled={isSyncingEvents}>
              <RefreshCw className={isSyncingEvents ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
              Синхронизировать события
            </Button>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="text-lg font-semibold text-foreground mb-2">Последний результат</h3>
          <p className="text-sm text-muted-foreground mb-4">Ответ backend после последней операции.</p>
          <pre className="text-xs bg-muted/50 rounded-lg p-4 overflow-auto max-h-80">
            {lastResult ? JSON.stringify(lastResult, null, 2) : 'Пока нет данных'}
          </pre>
        </div>
      </div>
    </MainLayout>
  );
}
