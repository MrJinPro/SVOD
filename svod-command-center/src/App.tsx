import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Navigate, useLocation } from "react-router-dom";
import { Suspense, lazy } from "react";
import { useApiGet } from "@/hooks/useApiGet";
const Index = lazy(() => import("./pages/Index"));
const Login = lazy(() => import("./pages/Login"));
const Events = lazy(() => import("./pages/Events"));
const Reports = lazy(() => import("./pages/Reports"));
const Users = lazy(() => import("./pages/Users"));
const Settings = lazy(() => import("./pages/Settings"));
const Integration = lazy(() => import("./pages/Integration"));
const Objects = lazy(() => import("./pages/Objects"));
const ObjectDetails = lazy(() => import("./pages/objects/ObjectDetails"));
const Analytics = lazy(() => import("./pages/Analytics"));
const AlarmAnalysis = lazy(() => import("./pages/AlarmAnalysis"));
const GbrReports = lazy(() => import("./pages/GbrReports"));
const GbrStatuses = lazy(() => import("./pages/GbrStatuses"));
const StaffEfficiency = lazy(() => import("./pages/StaffEfficiency"));
const Help = lazy(() => import("./pages/Help"));
const NotFound = lazy(() => import("./pages/NotFound"));
import { getAuthToken } from "./lib/api";

const queryClient = new QueryClient();

function RequireAuth({ children }: { children: JSX.Element }) {
  const location = useLocation();
  const token = getAuthToken();
  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

function RequireRole({
  roles,
  children,
}: {
  roles: Array<'admin' | 'analyst' | 'operator'>;
  children: JSX.Element;
}) {
  const { data: me, isLoading } = useApiGet('/auth/me', { role: 'operator' } as any);

  if (isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Загрузка…</div>;
  }

  const role = String((me as any)?.role || 'operator').trim() as any;
  if (roles.includes(role)) {
    return children;
  }
  return <Navigate to="/" replace />;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Загрузка…</div>}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<RequireAuth><Index /></RequireAuth>} />
            <Route path="/objects" element={<RequireAuth><Objects /></RequireAuth>} />
            <Route path="/objects/:objectId" element={<RequireAuth><ObjectDetails /></RequireAuth>} />
            <Route path="/events" element={<RequireAuth><Events /></RequireAuth>} />
            <Route path="/search" element={<Navigate to="/events" replace />} />
            <Route path="/reports" element={<RequireAuth><Reports /></RequireAuth>} />
            <Route path="/users" element={<RequireAuth><RequireRole roles={['admin']}><Users /></RequireRole></RequireAuth>} />
            <Route path="/analytics" element={<RequireAuth><RequireRole roles={['admin','analyst']}><Analytics /></RequireRole></RequireAuth>} />
            <Route path="/alarm-analysis" element={<RequireAuth><AlarmAnalysis /></RequireAuth>} />
            <Route path="/gbr-statuses" element={<RequireAuth><GbrStatuses /></RequireAuth>} />
            <Route path="/gbr-reports" element={<RequireAuth><GbrReports /></RequireAuth>} />
            <Route path="/staff" element={<RequireAuth><RequireRole roles={['admin','analyst']}><StaffEfficiency /></RequireRole></RequireAuth>} />
            <Route path="/integration" element={<RequireAuth><RequireRole roles={['admin']}><Integration /></RequireRole></RequireAuth>} />
            <Route path="/settings" element={<RequireAuth><RequireRole roles={['admin']}><Settings /></RequireRole></RequireAuth>} />
            <Route path="/help" element={<RequireAuth><Help /></RequireAuth>} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
