import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiPost } from '@/lib/api';
import { setStoredToken } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/hooks/use-toast';

type TokenResponse = {
  accessToken: string;
  tokenType: string;
  user: {
    id: string;
    username: string;
    email: string;
    role: string;
    isActive: boolean;
    lastLogin?: string | null;
  };
};

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async () => {
    const u = username.trim();
    if (!u || !password) return;

    setIsSubmitting(true);
    try {
      const res =
        mode === 'login'
          ? await apiPost<TokenResponse>('/auth/login', { username: u, password })
          : await apiPost<TokenResponse>('/auth/register', { username: u, password, email: email.trim() || undefined });

      setStoredToken(res.accessToken);
      toast({
        title: mode === 'login' ? 'Вход выполнен' : 'Регистрация выполнена',
        description: `Пользователь: ${res.user.username}`,
      });
      navigate('/', { replace: true });
    } catch (e: any) {
      toast({
        title: mode === 'login' ? 'Ошибка входа' : 'Ошибка регистрации',
        description: e?.message || 'Ошибка запроса',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 space-y-5">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold text-foreground">S.V.O.D</h1>
          <p className="text-sm text-muted-foreground">
            {mode === 'login' ? 'Вход в систему' : 'Регистрация пользователя'}
          </p>
        </div>

        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="username">Логин</Label>
            <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
          </div>

          {mode === 'register' && (
            <div className="space-y-2">
              <Label htmlFor="email">Email (необязательно)</Label>
              <Input id="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="password">Пароль</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
          </div>

          <Button className="w-full" onClick={submit} disabled={isSubmitting || !username.trim() || !password}>
            {mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </Button>

          <Button
            variant="ghost"
            className="w-full"
            onClick={() => setMode((m) => (m === 'login' ? 'register' : 'login'))}
            disabled={isSubmitting}
          >
            {mode === 'login' ? 'Нужен аккаунт? Регистрация' : 'Уже есть аккаунт? Войти'}
          </Button>
        </div>
      </div>
    </div>
  );
}
