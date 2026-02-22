// Event Types
export type EventSeverity = 'critical' | 'warning' | 'info' | 'success';
export type EventStatus = 'active' | 'pending' | 'resolved';
export type EventType = 'intrusion' | 'alarm' | 'access' | 'patrol' | 'incident' | 'maintenance';

export interface Event {
  id: string;
  timestamp: string;
  type: EventType;
  objectId?: string | null;
  objectName: string;
  clientName: string;
  severity: EventSeverity;
  status: EventStatus;
  code?: string | null;
  codeText?: string | null;
  stateName?: string | null;
  description: string;
  location?: string;
  operatorId?: string;

  // Agency archive fields (optional; not present for synthetic/demo events)
  resultText?: string | null;
  meterCount?: string | null;
  timeMeterCount?: string | null;
}

export interface EventAction {
  actionName: string;
  actionTime: string;
  operatorName?: string | null;
  computer?: string | null;
  gbrName?: string | null;
  dateKey?: number;
  rawEventId?: number;
  sourceTable?: string;
  sourcePk?: number;
}

export interface EventDetailsResponse {
  event: Event;
  actions: EventAction[];
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
export type ReportType = 'weekly' | 'monthly' | 'objectsByCode' | 'gbrRaportXlsx' | 'pcnLedger';
export type ReportStatus = 'generated' | 'sent' | 'pending' | 'failed';

export interface Report {
  id: string;
  type: ReportType;
  title?: string | null;
  periodStart: string;
  periodEnd: string;
  generatedAt: string;
  status: ReportStatus;
  eventsCount: number;
  criticalCount: number;

  downloadUrl?: string | null;
  fileName?: string | null;
  mimeType?: string | null;
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

// Analytics Types
export interface AnalyticsFiltersResponse {
  operators: string[];
  actionNames: string[];
  gbrNames: string[];
  dateMin: string | null;
  dateMax: string | null;
}

export interface OperatorHandlingRow {
  operator: string;
  events: number;
  avgSeconds: number;
  minSeconds: number;
  maxSeconds: number;
}

export interface OperatorActivityRow {
  bucket: string;
  operator: string;
  actions: number;
}

export interface OperatorLiveRow {
  operator: string;
  computer: string | null;
  online: boolean;
  lastActionAt: string | null;
  lastActionName: string | null;
  secondsSinceLastAction: number | null;
  actions5m: number;
  actions15m: number;
  actionsWindow: number;
  eventsWindow: number;
  avgHandlingSeconds: number | null;
  handledEvents: number;
  windowMinutes: number;
  onlineMinutes: number;
}

export interface GbrTripRow {
  eventId: string;
  agencyEventId?: string | null;
  gbrName: string;
  calledAt: string | null;
  arrivedAt: string | null;
  cancelledAt: string | null;
  lastActionAt: string | null;
  objectId: string | null;
  objectName: string | null;
  clientName: string | null;
  responsibleName?: string | null;
  calledOperator?: string | null;
  travelSeconds: number | null;

  meterCount?: string | null;
  timeMeterCount?: string | null;
  resultText?: string | null;

  tripStatus?: string | null;
}

export interface GbrTripsResponse {
  data: GbrTripRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface ObjectEventsSummaryResponse {
  objectId: string;
  total: number;
  bySeverity: Record<string, number>;
  byStatus: Record<string, number>;
  byCode: Array<{ codeGroup: number | null; code: string | null; codeText: string | null; count: number }>;
}
