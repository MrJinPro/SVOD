// Event Types
export type EventSeverity = 'critical' | 'warning' | 'info' | 'success';
export type EventStatus = 'active' | 'pending' | 'resolved';
export type EventType = 'intrusion' | 'alarm' | 'access' | 'patrol' | 'incident' | 'maintenance';

export interface Event {
  id: string;
  timestamp: string;
  type: EventType;
  objectName: string;
  clientName: string;
  severity: EventSeverity;
  status: EventStatus;
  description: string;
  location?: string;
  operatorId?: string;
}

// Report Types
export type ReportType = 'daily' | 'weekly' | 'monthly';
export type ReportStatus = 'generated' | 'sent' | 'pending' | 'failed';

export interface Report {
  id: string;
  type: ReportType;
  periodStart: string;
  periodEnd: string;
  generatedAt: string;
  status: ReportStatus;
  eventsCount: number;
  criticalCount: number;
}

// User Types
export type UserRole = 'operator' | 'admin' | 'analyst';

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  isActive: boolean;
  lastLogin?: string;
}

// Notification Types
export interface Notification {
  id: string;
  title: string;
  message: string;
  severity: EventSeverity;
  timestamp: string;
  read: boolean;
  eventId?: string;
}

// Dashboard Stats
export interface DashboardStats {
  totalEvents: number;
  criticalEvents: number;
  activeObjects: number;
  reportsGenerated: number;
  eventsTrend: number; // percentage change
}

// Filter Types
export interface EventFilters {
  dateFrom?: string;
  dateTo?: string;
  type?: EventType;
  severity?: EventSeverity;
  status?: EventStatus;
  objectId?: string;
  clientId?: string;
  search?: string;
}

// API Response Types
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, string>;
}
