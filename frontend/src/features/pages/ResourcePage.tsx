import type { ReactNode } from "react";
import { EmptyState, ErrorState, Loading } from "../../components/ui/Feedback";
import { Table } from "../../components/ui/Table";
import { useResource } from "../../hooks/useResource";
type Column<T> = { label: string; value: (item: T) => ReactNode };
export function ResourcePage<T>({ title, description, load, columns }: { title: string; description: string; load: () => Promise<T[]>; columns: Column<T>[] }) {
  const resource = useResource(load);
  return <><div className="mb-6"><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 text-sm text-slate-500">{description}</p></div>{resource.loading ? <Loading label={`Loading ${title.toLowerCase()}`}/> : resource.error ? <ErrorState message={resource.error} retry={() => void resource.retry()}/> : !resource.data?.length ? <EmptyState title={`No ${title.toLowerCase()} found`}>Records appear here when they are available in the backend.</EmptyState> : <Table headers={columns.map((c) => c.label)}>{resource.data.map((item, index) => <tr key={index}>{columns.map((column) => <td key={column.label} className="whitespace-nowrap px-4 py-3 text-slate-700">{column.value(item)}</td>)}</tr>)}</Table>}</>;
}
