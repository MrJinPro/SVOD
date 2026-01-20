import { MainLayout } from '@/components/layout/MainLayout';
import { ReportsTable } from '@/components/reports/ReportsTable';
import { useApiGet } from '@/hooks/useApiGet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, RefreshCw } from 'lucide-react';
import { API_BASE_URL } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import { useMemo, useState } from 'react';
import type { ReportStatus, ReportType } from '@/types';

export default function Reports() {
  const { data: reports, refetch } = useApiGet('/reports', []);

  const [typeFilter, setTypeFilter] = useState<'all' | ReportType>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | ReportStatus>('all');

  const defaultYear = new Date().getFullYear() - 1;
  const [phraseClient, setPhraseClient] = useState('');
  const [phraseYear, setPhraseYear] = useState(String(defaultYear));
  const [phraseA, setPhraseA] = useState('Снятие не по расписанию');
  const [phraseB, setPhraseB] = useState('Объект не поставлен под охрану по расписанию');

  const downloadDailyCsv = (date: string) => {
    const url = `${API_BASE_URL}/reports/export/daily?date=${encodeURIComponent(date)}`;
    window.location.href = url;
  };

  const downloadPhraseCountsCsv = () => {
    const params = new URLSearchParams();
    const yearInt = Number.parseInt(phraseYear, 10);
    if (!Number.isNaN(yearInt)) params.set('year', String(yearInt));
    if (phraseClient.trim()) params.set('clientName', phraseClient.trim());
    if (phraseA.trim()) params.set('phraseA', phraseA.trim());
    if (phraseB.trim()) params.set('phraseB', phraseB.trim());

    const url = `${API_BASE_URL}/reports/export/phrase-counts?${params.toString()}`;
    window.location.href = url;
  };

  const filteredReports = useMemo(() => {
    return (reports || []).filter((r: any) => {
      if (typeFilter !== 'all' && r.type !== typeFilter) return false;
      if (statusFilter !== 'all' && r.status !== statusFilter) return false;
      return true;
    });
  }, [reports, statusFilter, typeFilter]);

  const years = useMemo(() => {
    const now = new Date().getFullYear();
    return [now, now - 1, now - 2, now - 3, now - 4].map(String);
  }, []);

  return (
    <MainLayout 
      title="Отчёты" 
      subtitle="Сформированные и запланированные отчёты"
    >
      <div className="space-y-4 animate-fade-in">
        {/* Actions bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as any)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Тип отчёта" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все типы</SelectItem>
                <SelectItem value="daily">Суточные</SelectItem>
                <SelectItem value="weekly">Недельные</SelectItem>
                <SelectItem value="monthly">Месячные</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as any)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Статус" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все статусы</SelectItem>
                <SelectItem value="generated">Сформирован</SelectItem>
                <SelectItem value="sent">Отправлен</SelectItem>
                <SelectItem value="pending">Ожидает</SelectItem>
                <SelectItem value="failed">Ошибка</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2" onClick={refetch}>
              <RefreshCw className="h-4 w-4" />
              Обновить
            </Button>
            <Button
              size="sm"
              className="gap-2"
              onClick={() => {
                const today = new Date().toISOString().slice(0, 10);
                toast({
                  title: 'Отчёт',
                  description: 'Скачивание суточного отчёта (CSV).',
                });
                downloadDailyCsv(today);
              }}
            >
              <Plus className="h-4 w-4" />
              Создать отчёт
            </Button>
          </div>
        </div>

        {/* Phrase report filters */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-center gap-4">
            <Input
              className="w-[320px] bg-background"
              placeholder='Контрагент (например: ООО "Альбион 2002")'
              value={phraseClient}
              onChange={(e) => setPhraseClient(e.target.value)}
            />

            <Select value={phraseYear} onValueChange={setPhraseYear}>
              <SelectTrigger className="w-[140px] bg-background">
                <SelectValue placeholder="Год" />
              </SelectTrigger>
              <SelectContent>
                {years.map((y) => (
                  <SelectItem key={y} value={y}>
                    {y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Input
              className="w-[320px] bg-background"
              placeholder="Фраза 1"
              value={phraseA}
              onChange={(e) => setPhraseA(e.target.value)}
            />
            <Input
              className="w-[360px] bg-background"
              placeholder="Фраза 2"
              value={phraseB}
              onChange={(e) => setPhraseB(e.target.value)}
            />

            <Button
              variant="secondary"
              size="sm"
              className="gap-2"
              onClick={() => {
                toast({
                  title: 'Отчёт',
                  description: 'Скачивание выборки (CSV)…',
                });
                downloadPhraseCountsCsv();
              }}
            >
              Сформировать выборку
            </Button>
          </div>
        </div>

        {/* Table */}
        <ReportsTable reports={filteredReports} />
      </div>
    </MainLayout>
  );
}
