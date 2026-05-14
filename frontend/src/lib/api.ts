// Lightweight typed API client.
// All requests go through Next.js rewrites (/api -> FastAPI backend).

const TOKEN_KEY = "pk_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token === null) {
    window.localStorage.removeItem(TOKEN_KEY);
  } else {
    window.localStorage.setItem(TOKEN_KEY, token);
  }
}

export type ApiError = { detail: string; status: number };

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  isFormData = false,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (!isFormData) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    init.body = isFormData ? (body as FormData) : JSON.stringify(body);
  }

  const resp = await fetch(`/api${path}`, init);
  if (resp.status === 204) {
    return undefined as T;
  }
  const ct = resp.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await resp.json() : await resp.text();
  if (!resp.ok) {
    throw {
      detail: extractDetail(data, resp.status),
      status: resp.status,
    } satisfies ApiError;
  }
  return data as T;
}

function extractDetail(data: unknown, status: number): string {
  if (typeof data === "string" && data.length > 0) return data;
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      const msgs = d
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return typeof item === "string" ? item : "";
        })
        .filter((s) => s.length > 0);
      if (msgs.length > 0) return msgs.join("; ");
    }
  }
  return `request failed (${status})`;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  postForm: <T>(path: string, form: FormData) => request<T>("POST", path, form, true),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

// ----- typed payloads -----

export type UserMe = {
  id: number;
  email: string | null;
  first_name: string | null;
  username: string | null;
  timezone: string;
  currency: string;
  telegram_linked: boolean;
};

export type Category = {
  id: number;
  name: string;
  type: "in" | "out";
  emoji: string | null;
  is_default: boolean;
};

export type Transaction = {
  id: number;
  type: "in" | "out";
  amount: string;
  category_id: number | null;
  category_name: string | null;
  note: string | null;
  occurred_at: string;
};

export type CategoryTotal = {
  category_id: number | null;
  category_name: string;
  total: string;
};

export type Summary = {
  year: number;
  month: number;
  total_income: string;
  total_expense: string;
  balance: string;
  income_by_category: CategoryTotal[];
  expense_by_category: CategoryTotal[];
};

export type Budget = {
  id: number;
  category_id: number;
  category_name: string;
  monthly_limit: string;
  spent: string;
  remaining: string;
};

export type ReceiptOCR = {
  is_receipt: boolean;
  merchant: string;
  occurred_at: string | null;
  total_amount: string;
  currency: string;
  suggested_category: string;
  suggested_category_id: number | null;
  notes: string;
};

export type LinkCode = {
  code: string;
  expires_at: string;
};
