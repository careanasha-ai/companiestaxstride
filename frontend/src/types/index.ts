// ─── Auth & User ──────────────────────────────────────────────────────────────

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  phone: string | null;
  is_active: boolean;
  is_verified: boolean;
  tenant_id: number;
  created_at: string;
}

export interface AuthState {
  user: User | null;
  access_token: string | null;
  refresh_token: string | null;
  isAuthenticated: boolean;
}

// ─── Company ──────────────────────────────────────────────────────────────────

export interface Company {
  id: number;
  tenant_id: number;
  company_number: string;
  company_name: string;
  company_type: string | null;
  company_status: string | null;
  date_of_creation: string | null;
  registered_address_line1: string | null;
  registered_address_city: string | null;
  registered_address_postcode: string | null;
  vat_number: string | null;
  utr: string | null;
  is_vat_registered: boolean;
  is_dormant: boolean;
  next_confirmation_statement_due: string | null;
  next_accounts_due: string | null;
  last_synced_at: string | null;
  created_at: string;
}

export interface CompanySearchResult {
  company_number: string;
  company_name: string;
  company_status: string | null;
  company_type: string | null;
  date_of_creation: string | null;
  registered_office_address: {
    address_line_1?: string;
    address_line_2?: string;
    locality?: string;
    postal_code?: string;
    country?: string;
  } | null;
  sic_codes: string[];
}

export interface CompanyDetail extends CompanySearchResult {
  date_of_cessation: string | null;
  accounts: {
    next_due?: string;
    last_accounts?: { made_up_to?: string };
    accounting_reference_date?: { day?: number; month?: number };
  } | null;
  confirmation_statement: {
    next_due?: string;
    last_made_up_to?: string;
  } | null;
  officers: Officer[];
  persons_with_significant_control: PSC[];
  filing_history: FilingHistoryItem[];
}

export interface Officer {
  name: string;
  officer_role: string;
  appointed_on: string;
  resigned_on?: string;
  nationality?: string;
  occupation?: string;
  address?: Record<string, string>;
}

export interface PSC {
  name: string;
  kind: string;
  notified_on: string;
  ceased_on?: string;
  natures_of_control: string[];
  nationality?: string;
  country_of_residence?: string;
}

export interface FilingHistoryItem {
  transaction_id: string;
  type: string;
  description: string;
  date: string;
  category: string;
  links?: { document_metadata?: string };
}

// ─── Filings ──────────────────────────────────────────────────────────────────

export type FilingType = 'confirmation_statement' | 'annual_accounts' | 'vat_return' | 'ct600';
export type FilingStatus = 'draft' | 'pending_payment' | 'paid' | 'submitted' | 'accepted' | 'rejected';

export interface Filing {
  id: number;
  company_id: number;
  user_id: number;
  filing_type: FilingType;
  reference_number: string | null;
  made_up_to_date: string | null;
  period_start: string | null;
  period_end: string | null;
  status: FilingStatus;
  transaction_id: string | null;
  barcode: string | null;
  submitted_at: string | null;
  accepted_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  payment_id: number | null;
  created_at: string;
  company_name?: string;
  company_number?: string;
}

export interface Deadline {
  company_id: number;
  company_name: string;
  company_number: string;
  filing_type: FilingType;
  due_date: string;
  days_remaining: number;
  is_overdue: boolean;
  is_urgent: boolean;
}

// ─── VAT ──────────────────────────────────────────────────────────────────────

export interface VATReturn {
  id: number;
  company_id: number;
  period_key: string;
  period_start: string;
  period_end: string;
  due_date: string | null;
  box1_vat_due_sales: string;
  box2_vat_due_acquisitions: string;
  box3_total_vat_due: string;
  box4_vat_reclaimed: string;
  box5_net_vat_due: string;
  box6_total_sales: string;
  box7_total_purchases: string;
  box8_total_supplies: string;
  box9_total_acquisitions: string;
  status: string;
  submitted_at: string | null;
  hmrc_receipt_id: string | null;
  source: string | null;
  notes: string | null;
  created_at: string;
}

// ─── Payments ─────────────────────────────────────────────────────────────────

export interface Payment {
  id: number;
  tenant_id: number;
  user_id: number;
  filing_type: FilingType;
  amount: number;
  currency: string;
  provider: 'stripe' | 'paypal';
  status: string;
  description: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface Pricing {
  confirmation_statement: number;
  annual_accounts: number;
  vat_return: number;
  ct600: number;
  currency: string;
}

// ─── Integrations ─────────────────────────────────────────────────────────────

export interface Integration {
  id: number;
  tenant_id: number;
  company_id: number | null;
  provider: string;
  shop_domain: string | null;
  shop_name: string | null;
  is_active: boolean;
  auto_sync: boolean;
  last_synced_at: string | null;
  sync_status: 'idle' | 'syncing' | 'error';
  sync_error: string | null;
  created_at: string;
}

export interface ShopifyTransaction {
  id: number;
  shopify_order_id: string;
  shopify_order_number: string | null;
  order_date: string;
  customer_name: string | null;
  customer_country: string | null;
  subtotal: string;
  shipping: string;
  discount: string;
  total_price: string;
  currency: string;
  total_price_gbp: string;
  vat_amount: string;
  vat_rate: string;
  is_uk_sale: boolean;
  is_eu_sale: boolean;
  is_export: boolean;
  financial_status: string | null;
  vat_period_key: string | null;
}

// ─── UI Helpers ───────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string | { msg: string; type: string }[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}