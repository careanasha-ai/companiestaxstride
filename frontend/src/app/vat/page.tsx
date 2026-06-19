'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import {
  Receipt, ShoppingBag, RefreshCw, AlertTriangle, CheckCircle,
  TrendingUp, TrendingDown, Globe, MapPin, DollarSign,
  ArrowRight, Loader2, Info, ChevronDown, ChevronUp, Zap
} from 'lucide-react';
import { companiesApi, integrationsApi, vatApi } from '@/lib/api';
import { Company, Integration, VATReturn } from '@/types';
import { formatCurrency, formatDate, formatRelative, cn } from '@/lib/utils';
import { toast } from 'sonner';
import { format, subMonths, startOfMonth, endOfMonth } from 'date-fns';

// ─── VAT Box Component ────────────────────────────────────────────────────────

function VATBox({
  number, label, value, editable = false, fromShopify = false,
  onChange, hint
}: {
  number: number;
  label: string;
  value: string;
  editable?: boolean;
  fromShopify?: boolean;
  onChange?: (v: string) => void;
  hint?: string;
}) {
  return (
    <div className={cn(
      'rounded-lg border p-4',
      fromShopify ? 'bg-green-50 border-green-200' : 'bg-white border-gray-200',
      editable && !fromShopify ? 'bg-yellow-50 border-yellow-200' : ''
    )}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className="text-xs font-bold text-gray-400">BOX {number}</span>
          {fromShopify && (
            <span className="ml-2 rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700">
              Auto-filled
            </span>
          )}
          {editable && !fromShopify && (
            <span className="ml-2 rounded-full bg-yellow-100 px-1.5 py-0.5 text-xs font-medium text-yellow-700">
              Manual entry
            </span>
          )}
        </div>
      </div>
      <p className="text-xs text-gray-600 mb-2 leading-tight">{label}</p>
      {editable ? (
        <input
          type="number"
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          step="0.01"
          min="0"
          className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      ) : (
        <p className="text-lg font-bold text-gray-900">
          £{parseFloat(value || '0').toLocaleString('en-GB', { minimumFractionDigits: 2 })}
        </p>
      )}
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  );
}

// ─── Country Row ──────────────────────────────────────────────────────────────

function CountryRow({ cc, data }: { cc: string; data: any }) {
  const flag = cc.length === 2
    ? String.fromCodePoint(...[...cc.toUpperCase()].map(c => 0x1F1E6 + c.charCodeAt(0) - 65))
    : '🌍';
  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <div className="flex items-center gap-2">
        <span className="text-lg">{flag}</span>
        <div>
          <p className="text-sm font-medium text-gray-900">{data.country || cc}</p>
          <p className="text-xs text-gray-500">
            {data.orders} order{data.orders !== 1 ? 's' : ''} ·{' '}
            {data.is_uk ? '🇬🇧 UK' : data.is_eu ? '🇪🇺 EU' : '🌍 Export'}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-sm font-semibold text-gray-900">
          £{parseFloat(data.total_gbp).toLocaleString('en-GB', { minimumFractionDigits: 2 })}
        </p>
        {parseFloat(data.vat_gbp) > 0 && (
          <p className="text-xs text-green-600">
            VAT: £{parseFloat(data.vat_gbp).toFixed(2)}
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function VATDashboardPage() {
  const queryClient = useQueryClient();

  // Period selection
  const [periodStart, setPeriodStart] = useState(
    format(startOfMonth(subMonths(new Date(), 3)), 'yyyy-MM-dd')
  );
  const [periodEnd, setPeriodEnd] = useState(
    format(endOfMonth(subMonths(new Date(), 1)), 'yyyy-MM-dd')
  );

  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [selectedIntegrationId, setSelectedIntegrationId] = useState<number | null>(null);
  const [showCountries, setShowCountries] = useState(false);
  const [showCurrencies, setShowCurrencies] = useState(false);

  // Manual box overrides (Box 4 and Box 7)
  const [box4, setBox4] = useState('0.00');
  const [box7, setBox7] = useState('0.00');

  const { data: companies = [] } = useQuery({
    queryKey: ['companies'],
    queryFn: () => companiesApi.listMy().then((r) => r.data),
  });

  const { data: integrations = [] } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => integrationsApi.list().then((r) => r.data),
  });

  const shopifyIntegrations = integrations.filter(
    (i: Integration) => i.provider === 'shopify' && i.is_active
  );

  // VAT Aggregation query
  const {
    data: aggregation,
    isLoading: aggLoading,
    refetch: refetchAgg,
  } = useQuery({
    queryKey: ['vat-aggregation', selectedIntegrationId, periodStart, periodEnd],
    queryFn: () =>
      integrationsApi.shopifyVatAggregation(
        selectedIntegrationId!,
        periodStart,
        periodEnd
      ).then((r) => r.data),
    enabled: !!selectedIntegrationId,
  });

  // VAT Returns list
  const { data: vatReturns = [] } = useQuery({
    queryKey: ['vat-returns', selectedCompanyId],
    queryFn: () => vatApi.listReturns(selectedCompanyId!).then((r) => r.data),
    enabled: !!selectedCompanyId,
  });

  // Apply to VAT return mutation
  const applyMutation = useMutation({
    mutationFn: (vatReturnId: number) =>
      integrationsApi.applyVatAggregation(
        selectedIntegrationId!,
        periodStart,
        periodEnd,
        vatReturnId
      ).then((r) => r.data),
    onSuccess: (data) => {
      toast.success(`VAT return pre-filled! ${data.transaction_count} orders processed.`);
      queryClient.invalidateQueries({ queryKey: ['vat-returns'] });
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Failed to apply'),
  });

  const boxes = aggregation?.vat_boxes;
  const breakdown = aggregation?.breakdown;

  // Computed Box 5 with manual Box 4
  const box3 = parseFloat(boxes?.box3_total_vat_due || '0');
  const box4Val = parseFloat(box4 || '0');
  const box5Computed = Math.abs(box3 - box4Val).toFixed(2);
  const isRefund = box4Val > box3;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">VAT Dashboard</h1>
          <p className="text-gray-500 mt-1">
            Auto-calculate VAT from Shopify sales · Pre-fill MTD return boxes
          </p>
        </div>
        <Link
          href="/vat/submit"
          className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
        >
          <Receipt className="h-4 w-4" />
          Submit VAT Return
        </Link>
      </div>

      {/* Controls */}
      <div className="rounded-xl border bg-white p-5">
        <h2 className="font-semibold text-gray-900 mb-4">Select Period & Store</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Period Start</label>
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Period End</label>
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Company</label>
            <select
              value={selectedCompanyId || ''}
              onChange={(e) => setSelectedCompanyId(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Select company...</option>
              {companies.map((c: Company) => (
                <option key={c.id} value={c.id}>{c.company_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Shopify Store</label>
            <select
              value={selectedIntegrationId || ''}
              onChange={(e) => setSelectedIntegrationId(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Select store...</option>
              {shopifyIntegrations.map((i: Integration) => (
                <option key={i.id} value={i.id}>{i.shop_name || i.shop_domain}</option>
              ))}
            </select>
          </div>
        </div>

        {shopifyIntegrations.length === 0 && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-yellow-50 border border-yellow-200 p-3">
            <AlertTriangle className="h-4 w-4 text-yellow-500 flex-shrink-0" />
            <p className="text-xs text-yellow-700">
              No Shopify stores connected.{' '}
              <Link href="/settings/integrations" className="font-medium underline">
                Connect a store →
              </Link>
            </p>
          </div>
        )}
      </div>

      {/* Loading */}
      {aggLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-brand-600" />
          <span className="ml-3 text-gray-500">Aggregating Shopify sales data...</span>
        </div>
      )}

      {/* Aggregation Results */}
      {aggregation && !aggLoading && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                label: 'Total Orders',
                value: breakdown?.total_orders || 0,
                sub: `${breakdown?.uk_orders || 0} UK · ${breakdown?.eu_orders || 0} EU · ${breakdown?.export_orders || 0} Export`,
                icon: ShoppingBag,
                color: 'text-brand-600',
                bg: 'bg-brand-50',
              },
              {
                label: 'Total Sales (ex VAT)',
                value: `£${parseFloat(boxes?.box6_total_sales || '0').toLocaleString('en-GB', { minimumFractionDigits: 2 })}`,
                sub: 'Box 6 value',
                icon: TrendingUp,
                color: 'text-green-600',
                bg: 'bg-green-50',
              },
              {
                label: 'VAT Collected',
                value: `£${parseFloat(boxes?.box1_vat_due_sales || '0').toLocaleString('en-GB', { minimumFractionDigits: 2 })}`,
                sub: 'Box 1 — UK sales VAT',
                icon: Receipt,
                color: 'text-purple-600',
                bg: 'bg-purple-50',
              },
              {
                label: 'Net VAT Due',
                value: `£${parseFloat(box5Computed).toLocaleString('en-GB', { minimumFractionDigits: 2 })}`,
                sub: isRefund ? '← HMRC owes you' : '→ You owe HMRC',
                icon: isRefund ? TrendingDown : TrendingUp,
                color: isRefund ? 'text-green-600' : 'text-red-600',
                bg: isRefund ? 'bg-green-50' : 'bg-red-50',
              },
            ].map((stat) => {
              const Icon = stat.icon;
              return (
                <div key={stat.label} className="rounded-xl border bg-white p-5">
                  <div className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${stat.bg} mb-3`}>
                    <Icon className={`h-4 w-4 ${stat.color}`} />
                  </div>
                  <p className="text-xl font-bold text-gray-900">{stat.value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{stat.label}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{stat.sub}</p>
                </div>
              );
            })}
          </div>

          {/* MTD VAT Return Boxes */}
          <div className="rounded-xl border bg-white p-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-semibold text-gray-900">MTD VAT Return — Pre-filled Boxes</h2>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <span className="h-2.5 w-2.5 rounded-full bg-green-400 inline-block" />
                  Auto-filled from Shopify
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2.5 w-2.5 rounded-full bg-yellow-400 inline-block" />
                  Manual entry required
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mb-5">
              {aggregation.transaction_count} Shopify orders processed for period{' '}
              {formatDate(periodStart)} – {formatDate(periodEnd)}
            </p>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              <VATBox number={1} label="VAT due on sales and other outputs"
                value={boxes?.box1_vat_due_sales || '0'} fromShopify />
              <VATBox number={2} label="VAT due on acquisitions from EU member states"
                value={boxes?.box2_vat_due_acquisitions || '0'} fromShopify
                hint="Post-Brexit: usually £0" />
              <VATBox number={3} label="Total VAT due (Box 1 + Box 2)"
                value={boxes?.box3_total_vat_due || '0'} fromShopify />
              <VATBox number={4} label="VAT reclaimed on purchases and other inputs"
                value={box4} editable onChange={setBox4}
                hint="Enter your input VAT from purchases" />
              <VATBox number={5}
                label={`Net VAT ${isRefund ? 'reclaimable' : 'payable'} (|Box 3 − Box 4|)`}
                value={box5Computed}
                hint={isRefund ? 'HMRC will refund this amount' : 'Pay this to HMRC'} />
              <VATBox number={6} label="Total value of sales and all other outputs (ex VAT)"
                value={boxes?.box6_total_sales || '0'} fromShopify
                hint="Rounded to nearest £1 per HMRC rules" />
              <VATBox number={7} label="Total value of purchases and all other inputs (ex VAT)"
                value={box7} editable onChange={setBox7}
                hint="Enter your total purchases ex VAT" />
              <VATBox number={8} label="Total value of supplies to EU member states (ex VAT)"
                value={boxes?.box8_total_supplies || '0'} fromShopify
                hint="Post-Brexit B2B EU supplies only" />
              <VATBox number={9} label="Total value of acquisitions from EU member states (ex VAT)"
                value={boxes?.box9_total_acquisitions || '0'} fromShopify
                hint="Post-Brexit: usually £0" />
            </div>

            {/* Apply to VAT Return */}
            {vatReturns.length > 0 && (
              <div className="mt-5 pt-5 border-t">
                <p className="text-sm font-medium text-gray-700 mb-3">
                  Apply to existing VAT return draft:
                </p>
                <div className="flex flex-wrap gap-2">
                  {vatReturns
                    .filter((r: VATReturn) => r.status === 'draft')
                    .map((r: VATReturn) => (
                      <button
                        key={r.id}
                        onClick={() => applyMutation.mutate(r.id)}
                        disabled={applyMutation.isPending}
                        className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition-colors"
                      >
                        {applyMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Zap className="h-4 w-4" />
                        )}
                        Apply to {r.period_key} ({formatDate(r.period_start)} – {formatDate(r.period_end)})
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>

          {/* Warnings */}
          {aggregation.warnings?.length > 0 && (
            <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4">
              <h3 className="font-medium text-yellow-800 mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" /> Warnings
              </h3>
              <ul className="space-y-1">
                {aggregation.warnings.map((w: string, i: number) => (
                  <li key={i} className="text-sm text-yellow-700">• {w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Notes */}
          {aggregation.notes?.length > 0 && (
            <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
              <h3 className="font-medium text-blue-800 mb-2 flex items-center gap-2">
                <Info className="h-4 w-4" /> Notes
              </h3>
              <ul className="space-y-1">
                {aggregation.notes.map((n: string, i: number) => (
                  <li key={i} className="text-sm text-blue-700">• {n}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Sales Breakdown */}
          <div className="grid lg:grid-cols-2 gap-6">
            {/* By Sale Type */}
            <div className="rounded-xl border bg-white p-5">
              <h3 className="font-semibold text-gray-900 mb-4">Sales by Type</h3>
              <div className="space-y-3">
                {[
                  { label: 'UK Standard Rated (20%)', value: breakdown?.uk_standard_rated_sales, color: 'bg-blue-500' },
                  { label: 'UK Reduced Rated (5%)', value: breakdown?.uk_reduced_rated_sales, color: 'bg-blue-300' },
                  { label: 'UK Zero Rated', value: breakdown?.uk_zero_rated_sales, color: 'bg-blue-100' },
                  { label: 'EU Sales (zero-rated export)', value: breakdown?.eu_sales, color: 'bg-yellow-400' },
                  { label: 'Export (rest of world)', value: breakdown?.export_sales, color: 'bg-green-400' },
                ].map((item) => {
                  const val = parseFloat(item.value || '0');
                  const total = parseFloat(boxes?.box6_total_sales || '1');
                  const pct = total > 0 ? (val / total) * 100 : 0;
                  return (
                    <div key={item.label}>
                      <div className="flex justify-between text-xs text-gray-600 mb-1">
                        <span>{item.label}</span>
                        <span className="font-medium">
                          £{val.toLocaleString('en-GB', { minimumFractionDigits: 2 })}
                          {' '}({pct.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-gray-100">
                        <div
                          className={`h-2 rounded-full ${item.color}`}
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* By Country */}
            <div className="rounded-xl border bg-white p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900">Sales by Country</h3>
                <button
                  onClick={() => setShowCountries(!showCountries)}
                  className="text-xs text-brand-600 flex items-center gap-1"
                >
                  {showCountries ? 'Show less' : 'Show all'}
                  {showCountries ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
              </div>
              <div>
                {Object.entries(aggregation.country_summary || {})
                  .slice(0, showCountries ? undefined : 5)
                  .map(([cc, data]: [string, any]) => (
                    <CountryRow key={cc} cc={cc} data={data} />
                  ))}
                {Object.keys(aggregation.country_summary || {}).length === 0 && (
                  <p className="text-sm text-gray-400 text-center py-4">No country data</p>
                )}
              </div>
            </div>
          </div>

          {/* Currency Summary */}
          {Object.keys(aggregation.currency_summary || {}).length > 1 && (
            <div className="rounded-xl border bg-white p-5">
              <h3 className="font-semibold text-gray-900 mb-4">Multi-Currency Summary</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-xs text-gray-500">
                      <th className="text-left pb-2">Currency</th>
                      <th className="text-right pb-2">Orders</th>
                      <th className="text-right pb-2">Original Amount</th>
                      <th className="text-right pb-2">GBP Equivalent</th>
                      <th className="text-right pb-2">Avg Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(aggregation.currency_summary).map(([curr, data]: [string, any]) => (
                      <tr key={curr} className="border-b last:border-0">
                        <td className="py-2 font-medium">{curr}</td>
                        <td className="py-2 text-right text-gray-600">{data.orders}</td>
                        <td className="py-2 text-right text-gray-600">
                          {parseFloat(data.total_original).toLocaleString('en-GB', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-2 text-right font-medium">
                          £{parseFloat(data.total_gbp).toLocaleString('en-GB', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-2 text-right text-gray-500 text-xs">
                          {parseFloat(data.avg_rate).toFixed(6)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {!selectedIntegrationId && !aggLoading && (
        <div className="rounded-xl border bg-white p-12 text-center">
          <Receipt className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="font-semibold text-gray-900 mb-2">Select a Shopify store to begin</h3>
          <p className="text-sm text-gray-500 mb-6 max-w-md mx-auto">
            Choose a VAT period and your connected Shopify store above to automatically
            calculate your VAT return boxes from real sales data.
          </p>
          {shopifyIntegrations.length === 0 && (
            <Link
              href="/settings/integrations"
              className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
            >
              <ShoppingBag className="h-4 w-4" />
              Connect Shopify Store
            </Link>
          )}
        </div>
      )}
    </div>
  );
}