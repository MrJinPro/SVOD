import { MainLayout } from '@/components/layout/MainLayout';
import { User, UserRole } from '@/types';
import { useApiGet } from '@/hooks/useApiGet';
import { cn } from '@/lib/utils';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { MoreHorizontal, Plus, UserPlus } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const roleLabels: Record<UserRole, string> = {
  admin: 'Администратор',
  operator: 'Оператор',
  analyst: 'Аналитик',
};

const roleStyles: Record<UserRole, string> = {
  admin: 'bg-primary/10 text-primary border-primary/30',
  operator: 'bg-severity-info/10 text-severity-info border-severity-info/30',
  analyst: 'bg-severity-success/10 text-severity-success border-severity-success/30',
};

export default function Users() {
  const { data: users, refetch } = useApiGet('/users', []);

  const formatLastLogin = (dateString?: string) => {
    if (!dateString) return 'Никогда';
    return new Date(dateString).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <MainLayout 
      title="Пользователи" 
      subtitle="Управление учётными записями"
    >
      <div className="space-y-4 animate-fade-in">
        {/* Actions bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Всего: <strong className="text-foreground">{users.length}</strong> пользователей</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={refetch}
            >
              Обновить
            </Button>
            <Button
              size="sm"
              className="gap-2"
              onClick={() =>
                toast({
                  title: 'Пользователи',
                  description: 'Добавление пользователей будет добавлено в следующей версии прототипа.',
                })
              }
            >
            <UserPlus className="h-4 w-4" />
            Добавить пользователя
            </Button>
          </div>
        </div>

        {/* Table */}
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-border">
                <TableHead className="text-muted-foreground font-medium">Пользователь</TableHead>
                <TableHead className="text-muted-foreground font-medium">Email</TableHead>
                <TableHead className="text-muted-foreground font-medium">Роль</TableHead>
                <TableHead className="text-muted-foreground font-medium">Статус</TableHead>
                <TableHead className="text-muted-foreground font-medium">Последний вход</TableHead>
                <TableHead className="w-[60px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id} className="table-row-hover border-border">
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                        {user.username.slice(0, 2).toUpperCase()}
                      </div>
                      <span className="font-medium text-foreground">{user.username}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{user.email}</TableCell>
                  <TableCell>
                    <Badge className={cn('font-medium border', roleStyles[user.role])}>
                      {roleLabels[user.role]}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className={cn(
                        'h-2 w-2 rounded-full',
                        user.isActive ? 'bg-severity-success' : 'bg-muted-foreground'
                      )} />
                      <span className={cn(
                        'text-sm',
                        user.isActive ? 'text-severity-success' : 'text-muted-foreground'
                      )}>
                        {user.isActive ? 'Активен' : 'Неактивен'}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {formatLastLogin(user.lastLogin)}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => toast({ title: 'Редактирование', description: 'В прототипе недоступно.' })}
                        >
                          Редактировать
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => toast({ title: 'Сброс пароля', description: 'В прототипе недоступно.' })}
                        >
                          Сбросить пароль
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => toast({ title: 'Деактивация', description: 'В прототипе недоступно.' })}
                        >
                          Деактивировать
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </MainLayout>
  );
}
