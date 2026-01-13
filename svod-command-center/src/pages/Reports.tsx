import { MainLayout } from '@/components/layout/MainLayout';
import { ReportsTable } from '@/components/reports/ReportsTable';
import { useApiGet } from '@/hooks/useApiGet';
import { Button } from '@/components/ui/button';
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

export default function Reports() {
  const { data: reports, refetch } = useApiGet('/reports', []);

  const downloadDailyCsv = (date: string) => {
    const url = `${API_BASE_URL}/reports/export/daily?date=${encodeURIComponent(date)}`;
    window.location.href = url;
  };

  return (
    <MainLayout 
      title="Отчёты" 
      subtitle="Сформированные и запланированные отчёты"
    >
      <div className="space-y-4 animate-fade-in">
        {/* Actions bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Select defaultValue="all">
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
            <Select defaultValue="all">
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

        {/* Table */}
        <ReportsTable reports={reports} />
      </div>
    </MainLayout>
  );
}
