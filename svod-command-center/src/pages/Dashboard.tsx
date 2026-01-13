import { MainLayout } from '@/components/layout/MainLayout';
import { StatCard } from '@/components/dashboard/StatCard';
import { EventsChart } from '@/components/dashboard/EventsChart';
import { EventTypesChart } from '@/components/dashboard/EventTypesChart';
import { RecentEvents } from '@/components/dashboard/RecentEvents';
import { useApiGet } from '@/hooks/useApiGet';
import { AlertTriangle, Activity, Building2, FileText } from 'lucide-react';

export default function Dashboard() {
  const { data: stats } = useApiGet('/dashboard/stats', {
    totalEvents: 0,
    criticalEvents: 0,
    activeObjects: 0,
    reportsGenerated: 0,
    eventsTrend: 0,
  });

  return (
    <MainLayout 
      title="Панель управления" 
      subtitle="Обзор системы безопасности S.V.O.D"
    >
      <div className="space-y-6 animate-fade-in">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            title="Всего событий за сутки"
            value={stats.totalEvents}
            icon={Activity}
            trend={stats.eventsTrend}
            description="По сравнению со вчера"
          />
          <StatCard
            title="Критические события"
            value={stats.criticalEvents}
            icon={AlertTriangle}
            variant="critical"
            description="Требуют внимания"
          />
          <StatCard
            title="Активные объекты"
            value={stats.activeObjects}
            icon={Building2}
            description="Под охраной"
          />
          <StatCard
            title="Отчётов за неделю"
            value={stats.reportsGenerated}
            icon={FileText}
            variant="success"
            description="Сформировано"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            <EventsChart />
          </div>
          <EventTypesChart />
        </div>

        {/* Recent Events */}
        <RecentEvents />
      </div>
    </MainLayout>
  );
}
