import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, formatDistanceToNow, parseISO } from 'date-fns';
import { FilingType, FilingStatus } from '@/types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ─── Date Formatting ──────────────────────────────────────────────────────────

export function formatDate(date: string | null | undefined): string {
  if (!date) return '—';
  try {
    return format(parseISO(date), 'dd MMM yyyy');
  } catch {
    return date;
  }
}

export function formatDateTime(date: string | null | undefined): string {
  if (!date) return '—';
  try {
    return format(parseISO(date), 'dd MMM yyyy HH:mm');
  } catch {
    return date;
  }
}

export function formatRelative(date: string | null | undefined): string {
  if (!date) return '—';
  try {
    return formatDistanceToNow(parseISO(date), { addSuffix: true });
  } catch {
    return date;
  }
}

// ─── Currency Formatting ──────────────────────────────────────────────────────

export function formatCurrency(
  amount: number | string,
  currency = 'GBP'
): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(num);
}

export function formatPence(pence: number): string {
  return formatCurrency(pence / 100);
}

// ─── Filing Helpers ───────────────────────────────────────────────────────────

export const FILING_TYPE_LABELS: Record<FilingType, string> = {
  confirmation_statement: 'Confirmation Statement',
  annual_accounts: 'Annual Accounts',
  vat_return: 'VAT Return',
  ct600: 'Corporation Tax (CT600)',
};

export const FILING_STATUS_LABELS: Record<FilingStatus, string> = {
  draft: 'Draft',
  pending_payment: 'Pending Payment',
  paid: 'Paid',
  submitted: 'Submitted',
  accepted: 'Accepted',
  rejected: 'Rejected',
};

export const FILING_STATUS_COLORS: Record<FilingStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  pending_payment: 'bg-yellow-100 text-yellow-700',
  paid: 'bg-blue-100 text-blue-700',
  submitted: 'bg-purple-100 text-purple-700',
  accepted: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
};

export function getFilingTypeLabel(type: FilingType): string {
  return FILING_TYPE_LABELS[type] || type;
}

export function getStatusBadgeClass(status: FilingStatus): string {
  return FILING_STATUS_COLORS[status] || 'bg-gray-100 text-gray-700';
}

// ─── Company Helpers ──────────────────────────────────────────────────────────

export function formatCompanyNumber(num: string): string {
  // Pad to 8 characters
  return num.padStart(8, '0').toUpperCase();
}

export function getCompanyStatusColor(status: string | null): string {
  switch (status?.toLowerCase()) {
    case 'active': return 'text-green-600 bg-green-50';
    case 'dissolved': return 'text-red-600 bg-red-50';
    case 'liquidation': return 'text-orange-600 bg-orange-50';
    case 'dormant': return 'text-gray-600 bg-gray-50';
    default: return 'text-gray-600 bg-gray-50';
  }
}

// ─── VAT Helpers ──────────────────────────────────────────────────────────────

export function formatVATNumber(vat: string | null): string {
  if (!vat) return '—';
  const clean = vat.replace(/\s/g, '').toUpperCase();
  if (clean.startsWith('GB')) return clean;
  return `GB${clean}`;
}

// ─── Error Handling ───────────────────────────────────────────────────────────

export function getErrorMessage(error: unknown): string {
  if (!error) return 'An unknown error occurred';
  if (typeof error === 'string') return error;
  if (error instanceof Error) return error.message;
  const axiosError = error as { response?: { data?: { detail?: string | { msg: string }[] } } };
  const detail = axiosError?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ');
  return 'An unknown error occurred';
}

// ─── Deadline Helpers ─────────────────────────────────────────────────────────

export function getDeadlineColor(daysRemaining: number): string {
  if (daysRemaining < 0) return 'text-red-600';
  if (daysRemaining <= 14) return 'text-red-500';
  if (daysRemaining <= 30) return 'text-orange-500';
  if (daysRemaining <= 60) return 'text-yellow-600';
  return 'text-green-600';
}

export function getDeadlineBgColor(daysRemaining: number): string {
  if (daysRemaining < 0) return 'bg-red-50 border-red-200';
  if (daysRemaining <= 14) return 'bg-red-50 border-red-200';
  if (daysRemaining <= 30) return 'bg-orange-50 border-orange-200';
  if (daysRemaining <= 60) return 'bg-yellow-50 border-yellow-200';
  return 'bg-green-50 border-green-200';
}