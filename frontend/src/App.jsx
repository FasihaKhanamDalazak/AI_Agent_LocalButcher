import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import ChatPage from "./pages/ChatPage.jsx";
import StaffDashboardPage from "./pages/StaffDashboardPage.jsx";

/** Brief full-screen moment while a token from localStorage is being confirmed (GET /auth/me). */
function SessionLoader() {
  return (
    <div className="flex h-dvh items-center justify-center bg-background">
      <span className="text-2xl animate-pulse-dot rounded-full">🥩</span>
    </div>
  );
}

/**
 * /staff is a bare, unlinked path (no react-router — this is the one
 * exception, so a whole routing library wasn't worth adding for a single
 * internal page) — staff log in exactly like a customer, then navigate
 * here directly. StaffDashboardPage does its own role check for UX; the
 * backend's get_current_staff_user 403 is the actual security boundary.
 */
function AppShell() {
  const { isAuthenticated, isLoadingUser } = useAuth();
  const isStaffRoute = window.location.pathname === "/staff";

  if (!isAuthenticated) return <AuthPage />;
  if (isLoadingUser) return <SessionLoader />;
  if (isStaffRoute) return <StaffDashboardPage />;
  return <ChatPage />;
}

function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}

export default App;
