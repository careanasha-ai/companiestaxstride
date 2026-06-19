'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShoppingBag, Plus, RefreshCw, Trash2, CheckCircle,
  AlertCircle, Clock, ExternalLink, Loader2, Zap, Globe
} from 'lucide-react';
import { integrationsApi, companiesApi } from '@/lib/api';
import { Integration, Company } from '@/types';
import { formatRelative, formatDate, getErrorMessage } from '@/lib/utils';
import { toast } from 'sonner';

export default function IntegrationsPage() {
  const queryClient = useQueryClient();
  const [showConnectForm, setShowConnectForm] = useState(false);
  const [shopDomain, setShopDomain] = useState('');
  const [selectedCompanyId, setSelectedCompanyId] = useState('');

  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => integrationsApi.list().then((r) => r.data),
  });

  const { data: companies = [] } = useQuery({
    queryKey: ['companies'],
    queryFn: () => companiesApi.listMy().then((r) => r.data),
  });

  const connectMutation = useMutation({
    mutationFn: async () => {
      const shop = shopDomain.includes('.myshopify.com')
        ? shopDomain
        : `${shopDomain}.myshopify.com`;
      const res = await integrationsApi.shopifyInstall(shop, parseInt(selectedCompanyId));
      return res.data;
    },
    onSuccess: (data) => {
      // Redirect to Shopify OAuth
      window.location.href = data.install_url;
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const syncMutation = useMutation({
    mutationFn: (integrationId: number) =>
      integrationsApi.shopifySync(integrationId).then((r) => r.data),
    onSuccess: (data) => {
      toast.success(`Synced ${data.orders_synced} orders`);
      queryClient.invalidateQueries({ queryKey: ['integrations'] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const disconnectMutation = useMutation({
    mutationFn: (id: number) => integrationsApi.disconnect(id),
    onSuccess: () => {
      toast.success('Integration disconnected');
      queryClient.invalidateQueries({ queryKey: ['integrations'] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const getSyncStatusIcon = (status: string) => {
    switch (status) {
      case 'syncing': return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'error': return <AlertCircle className="h-4 w-4 text-red-500" />;
      default: return <CheckCircle className="h-4 w-4 text-green-500" />;
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Integrations</h1>
          <p className="text-gray-500 mt-1">
            Connect your ecommerce stores to auto-import sales data for VAT.
          </p>
        </div>
        <button
          onClick={() => setShowConnectForm(!showConnectForm)}
          className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Connect Store
        </button>
      </div>

      {/* Connect Form */}
      {showConnectForm && (
        <div className="rounded-xl border bg-white p-6 animate-fade-in">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <ShoppingBag className="h-5 w-5 text-green-600" />
            Connect Shopify Store
          </h2>
          <div className="grid sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Shopify Store Domain
              </label>
              <div className="flex">
                <input
                  type="text"
                  value={shopDomain}
                  onChange={(e) => setShopDomain(e.target.value)}
                  placeholder="mystore"
                  className="flex-1 rounded-l-lg border border-r-0 border-gray-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <span className="flex items-center rounded-r-lg border border-gray-300 bg-gray-50 px-3 text-sm text-gray-500">
                  .myshopify.com
                </span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Link to Company
              </label>
              <select
                value={selectedCompanyId}
                onChange={(e) => setSelectedCompanyId(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">Select company...</option>
                {companies.map((c: Company) => (
                  <option key={c.id} value={c.id}>
                    {c.company_name} ({c.company_number})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="rounded-lg bg-blue-50 border border-blue-100 p-3 mb-4">
            <p className="text-xs text-blue-700">
              <strong>What we'll access:</strong> Orders, products, customers, and financial data
              (read-only). We use this to calculate your VAT automatically.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => connectMutation.mutate()}
              disabled={!shopDomain || !selectedCompanyId || connectMutation.isPending}
              className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {connectMutation.isPending ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Connecting...</>
              ) : (
                <><ExternalLink className="h-4 w-4" /> Connect via Shopify</>
              )}
            </button>
            <button
              onClick={() => setShowConnectForm(false)}
              className="rounded-lg border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Available Integrations */}
      <div>
        <h2 className="font-semibold text-gray-900 mb-4">Available Integrations</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Shopify', icon: '🛒', status: 'available', color: 'bg-green-50 border-green-200' },
            { name: 'eBay', icon: '🏪', status: 'coming_soon', color: 'bg-gray-50 border-gray-200' },
            { name: 'WooCommerce', icon: '🛍️', status: 'coming_soon', color: 'bg-gray-50 border-gray-200' },
            { name: 'Amazon', icon: '📦', status: 'coming_soon', color: 'bg-gray-50 border-gray-200' },
            { name: 'Xero', icon: '📊', status: 'coming_soon', color: 'bg-gray-50 border-gray-200' },
            { name: 'QuickBooks', icon: '💼', status: 'coming_soon', color: 'bg-gray-50 border-gray-200' },
          ].map((item) => (
            <div key={item.name} className={`rounded-xl border p-4 ${item.color}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{item.icon}</span>
                  <span className="font-medium text-gray-900">{item.name}</span>
                </div>
                {item.status === 'available' ? (
                  <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                    Available
                  </span>
                ) : (
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                    Coming Soon
                  </span>
                )}
              </div>
              {item.status === 'available' && (
                <button
                  onClick={() => setShowConnectForm(true)}
                  className="mt-2 w-full rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 transition-colors"
                >
                  Connect
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Connected Integrations */}
      <div>
        <h2 className="font-semibold text-gray-900 mb-4">
          Connected Stores
          {integrations.length > 0 && (
            <span className="ml-2 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700">
              {integrations.length}
            </span>
          )}
        </h2>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
          </div>
        ) : integrations.length === 0 ? (
          <div className="rounded-xl border bg-white p-8 text-center">
            <Globe className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No stores connected yet</p>
            <p className="text-sm text-gray-400 mt-1">
              Connect your Shopify store to auto-import orders for VAT calculation.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {integrations.map((integration: Integration) => (
              <div key={integration.id} className="rounded-xl border bg-white p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 text-xl">
                      🛒
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-gray-900">
                          {integration.shop_name || integration.shop_domain}
                        </h3>
                        <div className="flex items-center gap-1">
                          {getSyncStatusIcon(integration.sync_status)}
                          <span className="text-xs text-gray-500 capitalize">
                            {integration.sync_status}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-gray-500 mt-0.5">
                        {integration.shop_domain}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        Last synced: {integration.last_synced_at
                          ? formatRelative(integration.last_synced_at)
                          : 'Never'}
                      </p>
                      {integration.sync_error && (
                        <p className="text-xs text-red-500 mt-1">
                          Error: {integration.sync_error}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => syncMutation.mutate(integration.id)}
                      disabled={syncMutation.isPending || integration.sync_status === 'syncing'}
                      className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                      Sync Now
                    </button>
                    <button
                      onClick={() => {
                        if (confirm('Disconnect this Shopify store?')) {
                          disconnectMutation.mutate(integration.id);
                        }
                      }}
                      className="flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Disconnect
                    </button>
                  </div>
                </div>

                {/* Quick stats */}
                <div className="mt-4 grid grid-cols-3 gap-3 pt-4 border-t">
                  <div className="text-center">
                    <p className="text-xs text-gray-500">Auto-sync</p>
                    <p className="text-sm font-medium text-gray-900">
                      {integration.auto_sync ? '✅ On' : '❌ Off'}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-500">Webhooks</p>
                    <p className="text-sm font-medium text-green-600">Active</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-500">Connected</p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatDate(integration.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}