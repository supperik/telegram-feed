import type { ReactNode } from "react";

export function Table({ children }: { children: ReactNode }) {
  return <table className="w-full text-sm border-collapse">{children}</table>;
}

export function Th({ children }: { children: ReactNode }) {
  return (
    <th className="text-left p-2 border-b border-gray-200 font-medium text-gray-700 bg-gray-50">
      {children}
    </th>
  );
}

export function Td({ children }: { children: ReactNode }) {
  return (
    <td className="p-2 border-b border-gray-100 align-top">{children}</td>
  );
}
