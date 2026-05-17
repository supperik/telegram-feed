import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiClient } from "../../shared/api/client";
import type { AdminActionsListResponse } from "../../shared/api/types";
import { Input } from "../../shared/ui/Input";
import { Button } from "../../shared/ui/Button";
import { Table, Th, Td } from "../../shared/ui/Table";

export function AuditScreen() {
  const [actionFilter, setActionFilter] = useState("");

  const query = useInfiniteQuery({
    queryKey: ["admin", "audit", actionFilter],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string> = { limit: "50" };
      if (actionFilter) params.action = actionFilter;
      if (pageParam) params.cursor = pageParam;
      const { data } = await apiClient.get<AdminActionsListResponse>(
        "/admin/admin-actions",
        { params },
      );
      return data;
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const rows = query.data?.pages.flatMap((p) => p.actions) ?? [];

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Audit log</h1>
        <Input
          placeholder="Filter by action (e.g. ban_channel)"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="max-w-xs"
        />
      </div>
      <div className="bg-white rounded shadow overflow-x-auto">
        <Table>
          <thead>
            <tr>
              <Th>ID</Th>
              <Th>Time</Th>
              <Th>Admin</Th>
              <Th>Action</Th>
              <Th>Target</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <Td>{a.id}</Td>
                <Td>{a.created_at.replace("T", " ").slice(0, 19)}</Td>
                <Td>{a.admin_email ?? `#${a.admin_id}`}</Td>
                <Td>
                  <code className="text-xs">{a.action}</code>
                </Td>
                <Td>
                  <pre className="text-xs whitespace-pre-wrap">
                    {JSON.stringify(a.target, null, 2)}
                  </pre>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
      {query.hasNextPage && (
        <Button
          onClick={() => query.fetchNextPage()}
          disabled={query.isFetchingNextPage}
          variant="secondary"
        >
          {query.isFetchingNextPage ? "Loading…" : "Load more"}
        </Button>
      )}
    </div>
  );
}
