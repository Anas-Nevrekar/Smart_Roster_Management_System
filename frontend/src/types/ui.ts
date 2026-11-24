import type { ReactNode } from "react";
export interface Column<T> { title: string; key: (row: T) => string; render: (row: T) => ReactNode; actions?: (row: T) => ReactNode }
