import { MainLayout } from '@/components/layout/MainLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Save, Server, Bell, Shield, Database } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from '@/hooks/use-toast';

const SETTINGS_KEY = 'svod_settings_v1';

type UiSettings = {
  apiUrl: string;
  apiTimeoutSec: number;
  pushEnabled: boolean;
  soundEnabled: boolean;
  emailEnabled: boolean;
  sessionTimeoutMin: number;
  autoLogout: boolean;
  refreshIntervalSec: number;
  autoRefresh: boolean;
};

const defaultSettings: UiSettings = {
  apiUrl: 'http://localhost:8000/api/v1',
  apiTimeoutSec: 30,
  pushEnabled: true,
  soundEnabled: true,
  emailEnabled: false,
  sessionTimeoutMin: 60,
  autoLogout: true,
  refreshIntervalSec: 30,
  autoRefresh: true,
};

export default function Settings() {
  const [settings, setSettings] = useState<UiSettings>(defaultSettings);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      if (raw) setSettings({ ...defaultSettings, ...(JSON.parse(raw) as Partial<UiSettings>) });
    } catch {
      // ignore
    }
  }, []);

  const save = () => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
      toast({ title: 'Настройки', description: 'Сохранено.' });
    } catch {
      toast({ title: 'Настройки', description: 'Не удалось сохранить.', variant: 'destructive' });
    }
  };

  return (
    <MainLayout 
      title="Настройки" 
      subtitle="Конфигурация системы"
    >
      <div className="max-w-3xl space-y-6 animate-fade-in">
        {/* API Configuration */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-lg bg-primary/10 p-2">
              <Server className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">API подключение</h3>
              <p className="text-sm text-muted-foreground">Настройки подключения к серверу</p>
            </div>
          </div>
          <Separator className="mb-4" />
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="api-url">URL сервера API</Label>
              <Input
                id="api-url"
                placeholder="https://api.svod.example.com"
                value={settings.apiUrl}
                onChange={(e) => setSettings((s) => ({ ...s, apiUrl: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="api-timeout">Таймаут запросов (сек)</Label>
              <Input
                id="api-timeout"
                type="number"
                value={String(settings.apiTimeoutSec)}
                onChange={(e) => setSettings((s) => ({ ...s, apiTimeoutSec: Number(e.target.value || 0) }))}
                className="w-32"
              />
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-lg bg-severity-warning/10 p-2">
              <Bell className="h-5 w-5 text-severity-warning" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Уведомления</h3>
              <p className="text-sm text-muted-foreground">Настройки оповещений</p>
            </div>
          </div>
          <Separator className="mb-4" />
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label>Push-уведомления</Label>
                <p className="text-sm text-muted-foreground">Получать уведомления в браузере</p>
              </div>
              <Switch checked={settings.pushEnabled} onCheckedChange={(v) => setSettings((s) => ({ ...s, pushEnabled: v }))} />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label>Звуковые оповещения</Label>
                <p className="text-sm text-muted-foreground">Звук при критических событиях</p>
              </div>
              <Switch checked={settings.soundEnabled} onCheckedChange={(v) => setSettings((s) => ({ ...s, soundEnabled: v }))} />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label>Email-уведомления</Label>
                <p className="text-sm text-muted-foreground">Дублировать на email</p>
              </div>
              <Switch checked={settings.emailEnabled} onCheckedChange={(v) => setSettings((s) => ({ ...s, emailEnabled: v }))} />
            </div>
          </div>
        </div>

        {/* Security */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-lg bg-severity-success/10 p-2">
              <Shield className="h-5 w-5 text-severity-success" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Безопасность</h3>
              <p className="text-sm text-muted-foreground">Параметры сессии</p>
            </div>
          </div>
          <Separator className="mb-4" />
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="session-timeout">Таймаут сессии (минут)</Label>
              <Input
                id="session-timeout"
                type="number"
                value={String(settings.sessionTimeoutMin)}
                onChange={(e) => setSettings((s) => ({ ...s, sessionTimeoutMin: Number(e.target.value || 0) }))}
                className="w-32"
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label>Автовыход при неактивности</Label>
                <p className="text-sm text-muted-foreground">Завершать сессию автоматически</p>
              </div>
              <Switch checked={settings.autoLogout} onCheckedChange={(v) => setSettings((s) => ({ ...s, autoLogout: v }))} />
            </div>
          </div>
        </div>

        {/* Data */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-lg bg-severity-info/10 p-2">
              <Database className="h-5 w-5 text-severity-info" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Данные</h3>
              <p className="text-sm text-muted-foreground">Кэширование и обновление</p>
            </div>
          </div>
          <Separator className="mb-4" />
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="refresh-interval">Интервал обновления (сек)</Label>
              <Input
                id="refresh-interval"
                type="number"
                value={String(settings.refreshIntervalSec)}
                onChange={(e) => setSettings((s) => ({ ...s, refreshIntervalSec: Number(e.target.value || 0) }))}
                className="w-32"
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label>Автообновление данных</Label>
                <p className="text-sm text-muted-foreground">Обновлять списки автоматически</p>
              </div>
              <Switch checked={settings.autoRefresh} onCheckedChange={(v) => setSettings((s) => ({ ...s, autoRefresh: v }))} />
            </div>
          </div>
        </div>

        {/* Save button */}
        <div className="flex justify-end">
          <Button className="gap-2" onClick={save}>
            <Save className="h-4 w-4" />
            Сохранить настройки
          </Button>
        </div>
      </div>
    </MainLayout>
  );
}
