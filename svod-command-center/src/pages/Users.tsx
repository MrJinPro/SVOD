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
import { MoreHorizontal, UserPlus } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { apiPatch, apiPost } from '@/lib/api';
import { useMemo, useState } from 'react';

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
  const { data: users, refetch, error, isLoading } = useApiGet('/users', []);
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [confirmToggleOpen, setConfirmToggleOpen] = useState(false);
  const [selected, setSelected] = useState<User | null>(null);

  const [formUsername, setFormUsername] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formRole, setFormRole] = useState<UserRole>('operator');
  const [formActive, setFormActive] = useState(true);
  const [formPassword, setFormPassword] = useState('');

  const canSubmitAdd = useMemo(() => formUsername.trim() && formPassword, [formUsername, formPassword]);

  const openAdd = () => {
    setSelected(null);
    setFormUsername('');
    setFormEmail('');
    setFormRole('operator');
    setFormActive(true);
    setFormPassword('');
    setAddOpen(true);
  };

  const openEdit = (u: User) => {
    setSelected(u);
    setFormUsername(u.username);
    setFormEmail(u.email || '');
    setFormRole(u.role);
    setFormActive(!!u.isActive);
    setEditOpen(true);
  };

  const openReset = (u: User) => {
    setSelected(u);
    setFormPassword('');
    setResetOpen(true);
  };

  const submitAdd = async () => {
    try {
      await apiPost('/users', {
        username: formUsername.trim(),
        password: formPassword,
        email: formEmail.trim() || null,
        role: formRole,
        isActive: formActive,
      });
      toast({ title: 'Пользователь', description: 'Создан.' });
      setAddOpen(false);
      refetch();
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e?.message || 'Ошибка запроса', variant: 'destructive' });
    }
  };

  const submitEdit = async () => {
    if (!selected) return;
    try {
      await apiPatch(`/users/${selected.id}`, {
        username: formUsername.trim(),
        email: formEmail.trim() || null,
        role: formRole,
        isActive: formActive,
      });
      toast({ title: 'Пользователь', description: 'Сохранено.' });
      setEditOpen(false);
      refetch();
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e?.message || 'Ошибка запроса', variant: 'destructive' });
    }
  };

  const submitReset = async () => {
    if (!selected) return;
    if (!formPassword) return;
    try {
      await apiPost(`/users/${selected.id}/password`, { password: formPassword });
      toast({ title: 'Пароль', description: 'Пароль обновлён.' });
      setResetOpen(false);
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e?.message || 'Ошибка запроса', variant: 'destructive' });
    }
  };

  const toggleActive = async () => {
    if (!selected) return;
    try {
      await apiPatch(`/users/${selected.id}`, { isActive: !selected.isActive });
      toast({ title: 'Пользователь', description: selected.isActive ? 'Деактивирован.' : 'Активирован.' });
      setConfirmToggleOpen(false);
      refetch();
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e?.message || 'Ошибка запроса', variant: 'destructive' });
    }
  };

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
        {error && (
          <div className="text-sm text-destructive">
            {error === 'Admin required' || error === 'Admin required.' || error.includes('Admin')
              ? 'Нет доступа: требуется роль администратора.'
              : `Ошибка загрузки: ${error}`}
          </div>
        )}

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
              disabled={isLoading}
            >
              Обновить
            </Button>
            <Button
              size="sm"
              className="gap-2"
              onClick={openAdd}
              disabled={!!error}
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
                  <TableCell className="text-muted-foreground">{user.email || 'нету'}</TableCell>
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
                          onClick={() => openEdit(user)}
                        >
                          Редактировать
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => openReset(user)}
                        >
                          Сбросить пароль
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => {
                            setSelected(user);
                            setConfirmToggleOpen(true);
                          }}
                        >
                          {user.isActive ? 'Деактивировать' : 'Активировать'}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Add dialog */}
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Добавить пользователя</DialogTitle>
              <DialogDescription>Создание новой учётной записи</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Логин</Label>
                <Input value={formUsername} onChange={(e) => setFormUsername(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Email (необязательно)</Label>
                <Input value={formEmail} onChange={(e) => setFormEmail(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Пароль</Label>
                <Input type="password" value={formPassword} onChange={(e) => setFormPassword(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Роль</Label>
                  <Select value={formRole} onValueChange={(v) => setFormRole(v as UserRole)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="operator">Оператор</SelectItem>
                      <SelectItem value="analyst">Аналитик</SelectItem>
                      <SelectItem value="admin">Администратор</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Активен</Label>
                  <div className="h-10 flex items-center">
                    <Switch checked={formActive} onCheckedChange={setFormActive} />
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddOpen(false)}>Отмена</Button>
              <Button onClick={submitAdd} disabled={!canSubmitAdd}>Создать</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit dialog */}
        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Редактировать пользователя</DialogTitle>
              <DialogDescription>{selected ? `Пользователь: ${selected.username}` : ''}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Логин</Label>
                <Input value={formUsername} onChange={(e) => setFormUsername(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Email (необязательно)</Label>
                <Input value={formEmail} onChange={(e) => setFormEmail(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Роль</Label>
                  <Select value={formRole} onValueChange={(v) => setFormRole(v as UserRole)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="operator">Оператор</SelectItem>
                      <SelectItem value="analyst">Аналитик</SelectItem>
                      <SelectItem value="admin">Администратор</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Активен</Label>
                  <div className="h-10 flex items-center">
                    <Switch checked={formActive} onCheckedChange={setFormActive} />
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditOpen(false)}>Отмена</Button>
              <Button onClick={submitEdit} disabled={!formUsername.trim()}>Сохранить</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Reset password dialog */}
        <Dialog open={resetOpen} onOpenChange={setResetOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Сбросить пароль</DialogTitle>
              <DialogDescription>{selected ? `Пользователь: ${selected.username}` : ''}</DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label>Новый пароль</Label>
              <Input type="password" value={formPassword} onChange={(e) => setFormPassword(e.target.value)} />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setResetOpen(false)}>Отмена</Button>
              <Button onClick={submitReset} disabled={!formPassword}>Обновить</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Confirm activate/deactivate */}
        <AlertDialog open={confirmToggleOpen} onOpenChange={setConfirmToggleOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{selected?.isActive ? 'Деактивировать пользователя?' : 'Активировать пользователя?'}</AlertDialogTitle>
              <AlertDialogDescription>
                {selected ? `Пользователь: ${selected.username}` : ''}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Отмена</AlertDialogCancel>
              <AlertDialogAction onClick={toggleActive}>Подтвердить</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </MainLayout>
  );
}
