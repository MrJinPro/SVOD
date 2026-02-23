import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Navigate, useLocation } from "react-router-dom";
import { Suspense, lazy } from "react";
const Index = lazy(() => import("./pages/Index"));
const Login = lazy(() => import("./pages/Login"));
const Events = lazy(() => import("./pages/Events"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const Reports = lazy(() => import("./pages/Reports"));
const Users = lazy(() => import("./pages/Users"));
const Settings = lazy(() => import("./pages/Settings"));
const Integration = lazy(() => import("./pages/Integration"));
const Objects = lazy(() => import("./pages/Objects"));
const ObjectDetails = lazy(() => import("./pages/objects/ObjectDetails"));
const Analytics = lazy(() => import("./pages/Analytics"));
const GbrReports = lazy(() => import("./pages/GbrReports"));
const GbrStatuses = lazy(() => import("./pages/GbrStatuses"));
const StaffEfficiency = lazy(() => import("./pages/StaffEfficiency"));
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
            <Route path="/search" element={<RequireAuth><SearchPage /></RequireAuth>} />
            <Route path="/reports" element={<RequireAuth><Reports /></RequireAuth>} />
            <Route path="/users" element={<RequireAuth><Users /></RequireAuth>} />
            <Route path="/analytics" element={<RequireAuth><Analytics /></RequireAuth>} />
            <Route path="/gbr-statuses" element={<RequireAuth><GbrStatuses /></RequireAuth>} />
            <Route path="/gbr-reports" element={<RequireAuth><GbrReports /></RequireAuth>} />
            <Route path="/staff" element={<RequireAuth><StaffEfficiency /></RequireAuth>} />
            <Route path="/integration" element={<RequireAuth><Integration /></RequireAuth>} />
            <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
