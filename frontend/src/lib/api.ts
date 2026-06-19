import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─── Axios Instance ───────────────────────────────────────────────────────────

const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

// ─── Request Interceptor: Attach JWT ─────────────────────────────────────────

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ─── Response Interceptor: Auto-refresh token ────────────────────────────────

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) throw new Error('No refresh token');
        const response = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
          refresh_token: refreshToken,
        });
        const { access_token, refresh_token } = response.data;
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/auth/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// ─── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
  register: (data: { email: string; password: string; full_name?: string; tenant_name: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
  updateMe: (data: { full_name?: string; phone?: string }) =>
    api.put('/auth/me', data),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
};

// ─── Companies API ────────────────────────────────────────────────────────────

export const companiesApi = {
  search: (q: string, page = 1, perPage = 20) =>
    api.get('/companies/search', { params: { q, page, per_page: perPage } }),
  lookup: (companyNumber: string) =>
    api.get(`/companies/lookup/${companyNumber}`),
  lookupFilingHistory: (companyNumber: string, category?: string, page = 1) =>
    api.get(`/companies/lookup/${companyNumber}/filing-history`, {
      params: { category, page },
    }),
  lookupOfficers: (companyNumber: string) =>
    api.get(`/companies/lookup/${companyNumber}/officers`),
  lookupPsc: (companyNumber: string) =>
    api.get(`/companies/lookup/${companyNumber}/psc`),
  listMy: () => api.get('/companies/my'),
  addCompany: (data: { company_number: string; vat_number?: string; utr?: string }) =>
    api.post('/companies/my', data),
  getMyCompany: (id: number) => api.get(`/companies/my/${id}`),
  updateCompany: (id: number, data: object) => api.put(`/companies/my/${id}`, data),
  syncCompany: (id: number) => api.post(`/companies/my/${id}/sync`),
  removeCompany: (id: number) => api.delete(`/companies/my/${id}`),
};

// ─── Filings API ──────────────────────────────────────────────────────────────

export const filingsApi = {
  list: (params?: { company_id?: number; filing_type?: string; status?: string }) =>
    api.get('/filings/', { params }),
  get: (id: number) => api.get(`/filings/${id}`),
  getDeadlines: () => api.get('/filings/deadlines/upcoming'),
  createConfirmationStatement: (data: object) =>
    api.post('/filings/confirmation-statement', data),
  submitConfirmationStatement: (id: number) =>
    api.post(`/filings/confirmation-statement/${id}/submit`),
  createAnnualAccounts: (data: object) =>
    api.post('/filings/annual-accounts', data),
  submitAnnualAccounts: (id: number) =>
    api.post(`/filings/annual-accounts/${id}/submit`),
};

// ─── VAT API ──────────────────────────────────────────────────────────────────

export const vatApi = {
  validateVatNumber: (vatNumber: string) =>
    api.get(`/vat/validate/${vatNumber}`),
  getHmrcAuthUrl: () => api.get('/vat/hmrc/auth-url'),
  getObligations: (companyId: number, params?: object) =>
    api.get(`/vat/obligations/${companyId}`, { params }),
  listReturns: (companyId: number) =>
    api.get(`/vat/returns/${companyId}`),
  createReturn: (companyId: number, data: object) =>
    api.post(`/vat/returns/${companyId}`, data),
  getReturn: (companyId: number, returnId: number) =>
    api.get(`/vat/returns/${companyId}/${returnId}`),
  updateReturn: (companyId: number, returnId: number, data: object) =>
    api.put(`/vat/returns/${companyId}/${returnId}`, data),
  submitReturn: (companyId: number, returnId: number) =>
    api.post(`/vat/returns/${companyId}/${returnId}/submit`),
  getLiabilities: (companyId: number, fromDate: string, toDate: string) =>
    api.get(`/vat/liabilities/${companyId}`, { params: { from_date: fromDate, to_date: toDate } }),
  getPayments: (companyId: number, fromDate: string, toDate: string) =>
    api.get(`/vat/payments/${companyId}`, { params: { from_date: fromDate, to_date: toDate } }),
};

// ─── Payments API ─────────────────────────────────────────────────────────────

export const paymentsApi = {
  getPricing: () => api.get('/payments/pricing'),
  getHistory: () => api.get('/payments/history'),
  createStripeIntent: (data: { filing_type: string; company_id: number; filing_id?: number }) =>
    api.post('/payments/stripe/create-intent', data),
  confirmStripePayment: (paymentIntentId: string, filingId?: number) =>
    api.post(`/payments/stripe/confirm/${paymentIntentId}`, null, {
      params: { filing_id: filingId },
    }),
  createPaypalOrder: (data: { filing_type: string; company_id: number; filing_id?: number }) =>
    api.post('/payments/paypal/create-order', data),
  capturePaypalOrder: (data: { order_id: string; filing_id?: number }) =>
    api.post('/payments/paypal/capture', data),
};

// ─── Integrations API ─────────────────────────────────────────────────────────

export const integrationsApi = {
  list: () => api.get('/integrations/'),
  disconnect: (id: number) => api.delete(`/integrations/${id}`),

  // Shopify OAuth
  shopifyInstall: (shop: string, companyId: number) =>
    api.get('/integrations/shopify/install', { params: { shop, company_id: companyId } }),

  // Shopify manual bulk sync
  shopifySync: (integrationId: number, sinceDate?: string) =>
    api.post(`/integrations/shopify/${integrationId}/sync`, null, {
      params: { since_date: sinceDate },
    }),

  // Shopify transactions list
  shopifyTransactions: (integrationId: number, params?: object) =>
    api.get(`/integrations/shopify/${integrationId}/transactions`, { params }),

  // Full VAT aggregation (pre-fills MTD boxes 1-9)
  shopifyVatAggregation: (integrationId: number, periodStart: string, periodEnd: string) =>
    api.get(`/integrations/shopify/${integrationId}/vat-aggregation`, {
      params: { period_start: periodStart, period_end: periodEnd },
    }),

  // Apply aggregation to a VAT return draft
  applyVatAggregation: (
    integrationId: number,
    periodStart: string,
    periodEnd: string,
    vatReturnId: number
  ) =>
    api.post(`/integrations/shopify/${integrationId}/vat-aggregation/apply`, null, {
      params: {
        period_start: periodStart,
        period_end: periodEnd,
        vat_return_id: vatReturnId,
      },
    }),

  // Legacy simple VAT summary
  shopifyVatSummary: (integrationId: number, periodStart: string, periodEnd: string) =>
    api.get(`/integrations/shopify/${integrationId}/vat-summary`, {
      params: { period_start: periodStart, period_end: periodEnd },
    }),

  // FX rates
  getFxRates: () => api.get('/integrations/fx-rates'),
};

// ─── Public API (no auth) ─────────────────────────────────────────────────────

export const publicApi = {
  getPricing: () => axios.get(`${API_URL}/api/v1/pricing`),
  searchCompanies: (q: string) =>
    axios.get(`${API_URL}/api/v1/companies/search`, { params: { q } }),
  lookupCompany: (companyNumber: string) =>
    axios.get(`${API_URL}/api/v1/companies/lookup/${companyNumber}`),
  validateVat: (vatNumber: string) =>
    axios.get(`${API_URL}/api/v1/vat/validate/${vatNumber}`),
};