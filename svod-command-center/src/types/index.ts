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

// Object Types
export interface ObjectListItem {
  id: string;
  name: string;
  address?: string;
  clientName?: string;
  disabled: boolean;
  lastEventAt?: string | null;
  eventsToday?: number;
}

export interface ObjectGroup {
  group: number;
  name?: string;
  isOpen?: boolean;
  timeEvent?: string | null;
}

export interface ObjectResponsible {
  id: string;
  name: string;
  address?: string;
  group?: number;
  order?: number;
  phones: string[];
}

export interface ObjectDetails {
  id: string;
  name: string;
  address?: string;
  clientName?: string;
  disabled: boolean;
  remarks?: string | null;
  additionalInfo?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  groups: ObjectGroup[];
  responsibles: ObjectResponsible[];
  stats?: {
    eventsTotal: number;
    eventsToday: number;
    lastEventAt?: string | null;
  };
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
  email?: string | null;
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
