import { lazy, Suspense } from "react";
import {
  createBrowserRouter,
  Navigate,
} from "react-router-dom";

const AppLayout = lazy(() => import("@/components/layout/AppLayout"));
const LoginPage = lazy(() => import("@/pages/auth/LoginPage"));
const RegisterPage = lazy(() => import("@/pages/auth/RegisterPage"));
const WaitlistPage = lazy(() => import("@/pages/auth/WaitlistPage"));
const ForgotPasswordPage = lazy(() => import("@/pages/auth/ForgotPasswordPage"));
const ChatPage = lazy(() => import("@/pages/ChatPage"));
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const CalendarPage = lazy(() => import("@/pages/CalendarPage"));
const EmailPage = lazy(() => import("@/pages/EmailPage"));
const TasksPage = lazy(() => import("@/pages/TasksPage"));
const KnowledgePage = lazy(() => import("@/pages/KnowledgePage"));
const CostsPage = lazy(() => import("@/pages/CostsPage"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));
const WaitlistAdmin = lazy(() => import("@/pages/admin/WaitlistAdmin"));

function LazyFallback() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  );
}

function SuspenseWrapper({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LazyFallback />}>{children}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <SuspenseWrapper><LoginPage /></SuspenseWrapper>,
  },
  {
    path: "/register",
    element: <SuspenseWrapper><RegisterPage /></SuspenseWrapper>,
  },
  {
    path: "/waitlist",
    element: <SuspenseWrapper><WaitlistPage /></SuspenseWrapper>,
  },
  {
    path: "/forgot-password",
    element: <SuspenseWrapper><ForgotPasswordPage /></SuspenseWrapper>,
  },
  {
    path: "/",
    element: <SuspenseWrapper><AppLayout /></SuspenseWrapper>,
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      {
        path: "chat",
        element: <SuspenseWrapper><ChatPage /></SuspenseWrapper>,
        handle: { layout: "custom" },
      },
      {
        path: "dashboard",
        element: <SuspenseWrapper><DashboardPage /></SuspenseWrapper>,
        handle: { layout: "standard" },
      },
      {
        path: "calendar",
        element: <SuspenseWrapper><CalendarPage /></SuspenseWrapper>,
        handle: { layout: "fullscreen" },
      },
      {
        path: "email",
        element: <SuspenseWrapper><EmailPage /></SuspenseWrapper>,
        handle: { layout: "custom" },
      },
      {
        path: "tasks",
        element: <SuspenseWrapper><TasksPage /></SuspenseWrapper>,
        handle: { layout: "standard" },
      },
      {
        path: "knowledge",
        element: <SuspenseWrapper><KnowledgePage /></SuspenseWrapper>,
        handle: { layout: "standard" },
      },
      {
        path: "costs",
        element: <SuspenseWrapper><CostsPage /></SuspenseWrapper>,
        handle: { layout: "standard" },
      },
      {
        path: "settings",
        element: <SuspenseWrapper><SettingsPage /></SuspenseWrapper>,
        handle: { layout: "standard" },
      },
      {
        path: "admin/waitlist",
        element: <SuspenseWrapper><WaitlistAdmin /></SuspenseWrapper>,
        handle: { layout: "standard" },
      },
    ],
  },
]);
