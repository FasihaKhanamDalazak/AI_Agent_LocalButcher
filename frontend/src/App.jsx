import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import ChatPage from "./pages/ChatPage.jsx";

/** Brief full-screen moment while a token from localStorage is being confirmed (GET /auth/me). */
function SessionLoader() {
  return (
    <div className="flex h-dvh items-center justify-center bg-background">
      <span className="text-2xl animate-pulse-dot rounded-full">🥩</span>
    </div>
  );
}

function AppShell() {
  const { isAuthenticated, isLoadingUser } = useAuth();

  if (!isAuthenticated) return <AuthPage />;
  if (isLoadingUser) return <SessionLoader />;
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
