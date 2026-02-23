import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Building2,
  AlertTriangle,
  Search,
  FileText,
  Users,
  BarChart3,
  Activity,
  Settings,
  Database,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useApiGet } from '@/hooks/useApiGet';
import { clearStoredToken } from '@/lib/auth';

const navigation = [
  { name: 'Панель управления', href: '/', icon: LayoutDashboard },
  { name: 'Объекты', href: '/objects', icon: Building2 },
  { name: 'События', href: '/events', icon: AlertTriangle },
  { name: 'Поиск', href: '/search', icon: Search },
  { name: 'Отчёты', href: '/reports', icon: FileText },
  { name: 'Аналитика', href: '/analytics', icon: BarChart3 },
  { name: 'Статусы ГБР', href: '/gbr-statuses', icon: Activity },
  { name: 'Отчёт ГБР', href: '/gbr-reports', icon: BarChart3 },
  { name: 'Эффективность', href: '/staff', icon: Activity },
  { name: 'Пользователи', href: '/users', icon: Users },
];

const bottomNavigation = [
  { name: 'Интеграция', href: '/integration', icon: Database },
  { name: 'Настройки', href: '/settings', icon: Settings },
];
export function Sidebar({
  collapsed,
  onToggleCollapsed,
}: {
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { data: me } = useApiGet('/auth/me', { username: '', role: 'operator', email: null } as any);

  const canSeeAnalytics = (() => {
    const role = String((me as any)?.role || '').trim();
    if (role === 'admin' || role === 'analyst') return true;
    const perms = ((me as any)?.permissions || []) as string[];
    return Array.isArray(perms) && perms.includes('analytics:read');
  })();

  const canSeeUsers = (() => {
    const role = String((me as any)?.role || '').trim();
    if (role === 'admin') return true;
    const perms = ((me as any)?.permissions || []) as string[];
    if (!Array.isArray(perms)) return false;
    return perms.includes('users:read') || perms.includes('users:write') || perms.includes('rbac:manage');
  })();

  const roleLabel = (role: string) => {
    if (role === 'admin') return 'Администратор';
    if (role === 'analyst') return 'Аналитик';
    return 'Оператор';
  };

  const initials = (() => {
    const u = String((me as any)?.username || '').trim();
    if (!u) return '??';
    return u.slice(0, 2).toUpperCase();
  })();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-sidebar border-r border-sidebar-border transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-sidebar-border">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary glow-primary">
              <img src="/icon.png" alt="SVOD" className="h-5 w-5" />
            </div>
            {!collapsed && (
              <div className="flex flex-col">
                <span className="text-lg font-bold text-foreground tracking-tight">S.V.O.D</span>
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest">Security System</span>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-2 py-4">
          {navigation
            .filter((item) => {
              if (item.href === '/analytics' || item.href === '/gbr-statuses' || item.href === '/gbr-reports' || item.href === '/staff') return canSeeAnalytics;
              if (item.href === '/users') return canSeeUsers;
              return true;
            })
            .map((item) => {
            const isActive = location.pathname === item.href;
            const badge = undefined;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={cn(
                  'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-primary'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                )}
              >
                <item.icon className={cn('h-5 w-5 flex-shrink-0', isActive && 'text-primary')} />
                {!collapsed && (
                  <>
                    <span className="flex-1">{item.name}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="border-t border-sidebar-border px-2 py-4 space-y-1">
          {bottomNavigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={cn(
                  'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-primary'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                )}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" />
                {!collapsed && <span>{item.name}</span>}
              </NavLink>
            );
          })}

          <Separator className="my-2 bg-sidebar-border" />

          {/* User section */}
          <div className={cn('flex items-center gap-3 rounded-lg px-3 py-2', collapsed && 'justify-center')}>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-primary text-sm font-semibold">
              {initials}
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{(me as any)?.username || ''}</p>
                <p className="text-xs text-muted-foreground">{roleLabel((me as any)?.role || 'operator')}</p>
              </div>
            )}
            <Button
              variant="ghost"
              size="icon"
              className={cn('h-8 w-8 text-muted-foreground hover:text-foreground', collapsed && 'ml-0')}
              onClick={() => {
                clearStoredToken();
                navigate('/login');
              }}
              title="Выйти"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Collapse button */}
        <Button
          variant="ghost"
          size="icon"
          className="absolute -right-3 top-20 h-6 w-6 rounded-full border border-border bg-background shadow-md hover:bg-accent"
          onClick={onToggleCollapsed}
        >
          {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
        </Button>
      </div>
    </aside>
  );
}
