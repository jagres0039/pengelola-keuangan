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

export type ProfileMode = "standar" | "pengusaha";

export type UserMe = {
  id: number;
  email: string | null;
  first_name: string | null;
  username: string | null;
  timezone: string;
  currency: string;
  telegram_linked: boolean;
  low_balance_threshold: string;
  is_admin: boolean;
  profile_mode: ProfileMode;
};

export type Category = {
  id: number;
  name: string;
  type: "in" | "out";
  emoji: string | null;
  is_default: boolean;
};

export type TransactionItem = {
  id: number;
  name: string;
  qty: string;
  unit_price: string | null;
  subtotal: string;
};

export type Transaction = {
  id: number;
  type: "in" | "out";
  amount: string;
  category_id: number | null;
  category_name: string | null;
  account_id: number | null;
  account_name: string | null;
  note: string | null;
  occurred_at: string;
  items: TransactionItem[];
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

export type ReceiptOCRItem = {
  name: string;
  qty: string;
  unit_price: string | null;
  subtotal: string;
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
  items: ReceiptOCRItem[];
};

export type LinkCode = {
  code: string;
  expires_at: string;
};

export type LowBalanceStatus = {
  is_low: boolean;
  balance: string;
  threshold: string;
  total_income: string;
  total_expense: string;
};

export type ImportPreviewRow = {
  action: string;
  row_index: number | null;
  transaction_id: number | null;
  type: string;
  amount: string;
  category_name: string;
  note: string | null;
  occurred_at: string | null;
};

export type ImportPreviewResponse = {
  plan_id: string;
  to_create: ImportPreviewRow[];
  to_update: ImportPreviewRow[];
  to_delete: ImportPreviewRow[];
  errors: string[];
};

export type ImportApplyResponse = {
  created: number;
  updated: number;
  deleted: number;
};

export type SubscriptionStatus = {
  state: "trial" | "active" | "expired";
  active: boolean;
  can_write: boolean;
  expires_at: string | null;
  days_left: number;
  has_pending_payment: boolean;
  monthly_price: string;
  currency: string;
  billing_instructions: string;
};

export type Payment = {
  id: number;
  amount: string;
  method: string;
  proof_note: string | null;
  status: "pending" | "approved" | "rejected";
  period_start: string | null;
  period_end: string | null;
  decided_at: string | null;
  rejection_reason: string | null;
  created_at: string;
};

export type AdminPayment = Payment & {
  user_id: number;
  user_email: string | null;
  user_first_name: string | null;
};

export type ContactKind = "customer" | "supplier" | "both";

export type Contact = {
  id: number;
  name: string;
  kind: ContactKind;
  phone: string | null;
  address: string | null;
  notes: string | null;
  archived: boolean;
  created_at: string;
};

export type ContactCreatePayload = {
  name: string;
  kind: ContactKind;
  phone?: string;
  address?: string;
  notes?: string;
};

export type ContactUpdatePayload = Partial<ContactCreatePayload>;

export type AccountKind = "cash" | "bank" | "ewallet" | "other";

export type Account = {
  id: number;
  name: string;
  kind: AccountKind;
  opening_balance: string;
  balance: string;
  archived: boolean;
  created_at: string;
};

export type AccountCreatePayload = {
  name: string;
  kind: AccountKind;
  opening_balance?: string;
};

export type AccountUpdatePayload = Partial<AccountCreatePayload>;

export type Transfer = {
  id: number;
  from_account_id: number;
  from_account_name: string;
  to_account_id: number;
  to_account_name: string;
  amount: string;
  note: string | null;
  occurred_at: string;
  created_at: string;
};

export type TransferCreatePayload = {
  from_account_id: number;
  to_account_id: number;
  amount: string;
  note?: string;
  occurred_at?: string;
};

export type MovementReason = "purchase" | "sale" | "adjustment" | "initial";

export type InventoryItem = {
  id: number;
  name: string;
  sku: string | null;
  unit: string;
  stock: string;
  last_cost: string | null;
  archived: boolean;
  created_at: string;
};

export type InventoryItemCreatePayload = {
  name: string;
  sku?: string;
  unit?: string;
  initial_stock?: string;
  initial_cost?: string;
};

export type InventoryItemUpdatePayload = {
  name?: string;
  sku?: string;
  unit?: string;
};

export type InventoryMovement = {
  id: number;
  inventory_item_id: number;
  qty_delta: string;
  unit_cost: string | null;
  reason: MovementReason;
  note: string | null;
  occurred_at: string;
  created_at: string;
};

export type InventoryMovementCreatePayload = {
  qty_delta: string;
  unit_cost?: string;
  reason: MovementReason;
  note?: string;
  occurred_at?: string;
};
