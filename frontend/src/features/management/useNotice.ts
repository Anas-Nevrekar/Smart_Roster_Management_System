import { useCallback, useState } from "react";
export function useNotice() { const [message, setMessage] = useState<string | null>(null); const dismiss = useCallback(() => setMessage(null), []); return { message, setMessage, dismiss }; }
