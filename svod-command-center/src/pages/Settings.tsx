import { MainLayout } from '@/components/layout/MainLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Save, Server, Bell, Shield, Database } from 'lucide-react';

export default function Settings() {
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
                defaultValue="https://api.svod.example.com"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="api-timeout">Таймаут запросов (сек)</Label>
              <Input
                id="api-timeout"
                type="number"
                defaultValue="30"
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
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label>Звуковые оповещения</Label>
                <p className="text-sm text-muted-foreground">Звук при критических событиях</p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label>Email-уведомления</Label>
                <p className="text-sm text-muted-foreground">Дублировать на email</p>
              </div>
              <Switch />
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
                defaultValue="60"
                className="w-32"
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label>Автовыход при неактивности</Label>
                <p className="text-sm text-muted-foreground">Завершать сессию автоматически</p>
              </div>
              <Switch defaultChecked />
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
                defaultValue="30"
                className="w-32"
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label>Автообновление данных</Label>
                <p className="text-sm text-muted-foreground">Обновлять списки автоматически</p>
              </div>
              <Switch defaultChecked />
            </div>
          </div>
        </div>

        {/* Save button */}
        <div className="flex justify-end">
          <Button className="gap-2">
            <Save className="h-4 w-4" />
            Сохранить настройки
          </Button>
        </div>
      </div>
    </MainLayout>
  );
}
