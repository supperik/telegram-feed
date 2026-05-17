import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import type { AnyRouter } from "@tanstack/react-router";
import type { ReactNode } from "react";

export function Providers({
  router,
  children,
}: {
  router: AnyRouter;
  children?: ReactNode;
}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
      {children}
    </QueryClientProvider>
  );
}
