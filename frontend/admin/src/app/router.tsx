import {
  createRootRoute,
  createRoute,
  createRouter,
  Link,
  Outlet,
  redirect,
  useNavigate,
} from "@tanstack/react-router";
import { useAuthStore } from "../shared/auth/store";
import { LoginScreen } from "../features/login/LoginScreen";
import { ChannelsScreen } from "../features/channels/ChannelsScreen";
import { StatsScreen } from "../features/stats/StatsScreen";
import { AuditScreen } from "../features/audit/AuditScreen";

function TopBar() {
  const navigate = useNavigate();
  const clear = useAuthStore((s) => s.clear);
  const onSignOut = () => {
    clear();
    navigate({ to: "/login" });
  };
  const linkClass =
    "text-sm text-gray-700 hover:text-gray-900 px-2 py-1 rounded";
  const activeClass = "bg-gray-200 font-medium";
  return (
    <header className="bg-white border-b border-gray-200">
      <nav className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-4">
        <span className="font-semibold text-gray-900 mr-4">Admin</span>
        <Link
          to="/channels"
          className={linkClass}
          activeProps={{ className: `${linkClass} ${activeClass}` }}
        >
          Channels
        </Link>
        <Link
          to="/stats"
          className={linkClass}
          activeProps={{ className: `${linkClass} ${activeClass}` }}
        >
          Stats
        </Link>
        <Link
          to="/audit"
          className={linkClass}
          activeProps={{ className: `${linkClass} ${activeClass}` }}
        >
          Audit
        </Link>
        <button
          onClick={onSignOut}
          className="ml-auto text-sm text-gray-700 hover:text-gray-900 px-2 py-1 rounded"
        >
          Sign out
        </button>
      </nav>
    </header>
  );
}

function ProtectedLayout() {
  return (
    <>
      <TopBar />
      <main>
        <Outlet />
      </main>
    </>
  );
}

const requireAuth = () => {
  if (!useAuthStore.getState().accessToken) {
    throw redirect({ to: "/login" });
  }
};

const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginScreen,
});

const protectedRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "protected",
  beforeLoad: requireAuth,
  component: ProtectedLayout,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({
      to: useAuthStore.getState().accessToken ? "/channels" : "/login",
    });
  },
});

const channelsRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/channels",
  component: ChannelsScreen,
});

const statsRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/stats",
  component: StatsScreen,
});

const auditRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/audit",
  component: AuditScreen,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  protectedRoute.addChildren([channelsRoute, statsRoute, auditRoute]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
