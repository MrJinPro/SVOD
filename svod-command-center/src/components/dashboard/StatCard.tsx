import { cn } from '@/lib/utils';
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: number;
  variant?: 'default' | 'critical' | 'warning' | 'success';
  description?: string;
}

const variantStyles = {
  default: {
    icon: 'bg-primary/10 text-primary',
    glow: '',
  },
  critical: {
    icon: 'bg-severity-critical/10 text-severity-critical',
    glow: 'glow-critical',
  },
  warning: {
    icon: 'bg-severity-warning/10 text-severity-warning',
    glow: '',
  },
  success: {
    icon: 'bg-severity-success/10 text-severity-success',
    glow: '',
  },
};

export function StatCard({ title, value, icon: Icon, trend, variant = 'default', description }: StatCardProps) {
  const styles = variantStyles[variant];

  return (
    <div className={cn(
      'relative overflow-hidden rounded-xl border border-border bg-card p-6 transition-all duration-200 hover:border-primary/30',
      variant === 'critical' && 'border-severity-critical/30'
    )}>
      {/* Background decoration */}
      <div className="absolute -right-4 -top-4 h-24 w-24 rounded-full bg-gradient-to-br from-primary/5 to-transparent" />
      
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <div className="flex items-baseline gap-2">
            <span className={cn(
              'text-3xl font-bold tracking-tight',
              variant === 'critical' ? 'text-severity-critical' : 'text-foreground'
            )}>
              {value}
            </span>
            {trend !== undefined && (
              <span className={cn(
                'flex items-center gap-0.5 text-sm font-medium',
                trend >= 0 ? 'text-severity-success' : 'text-severity-critical'
              )}>
                {trend >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {Math.abs(trend)}%
              </span>
            )}
          </div>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        <div className={cn('rounded-xl p-3', styles.icon, styles.glow)}>
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </div>
  );
}
