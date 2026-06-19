import Link from 'next/link';
import {
  Building2, Search, FileText, Receipt, ShoppingBag,
  CheckCircle, ArrowRight, Shield, Zap, Globe
} from 'lucide-react';

const features = [
  {
    icon: Search,
    title: 'Free Company Lookup',
    description: 'Search any UK company, view officers, PSC, filing history, and accounts — completely free.',
    free: true,
  },
  {
    icon: FileText,
    title: 'Confirmation Statement',
    description: 'File your CS01 Confirmation Statement directly with Companies House.',
    free: false,
    price: '£14.99',
  },
  {
    icon: FileText,
    title: 'Annual Accounts',
    description: 'Submit micro-entity, small, or full annual accounts. ECCT Act 2023 compliant.',
    free: false,
    price: '£24.99',
  },
  {
    icon: Receipt,
    title: 'VAT Returns (MTD)',
    description: 'Making Tax Digital compliant VAT return submission directly to HMRC.',
    free: false,
    price: '£9.99',
  },
  {
    icon: ShoppingBag,
    title: 'Shopify Integration',
    description: 'Auto-import Shopify orders to calculate VAT. Supports multi-currency.',
    free: true,
  },
  {
    icon: Shield,
    title: 'Secure & Compliant',
    description: 'Bank-grade encryption. GDPR compliant. Your data is never sold.',
    free: true,
  },
];

const pricingItems = [
  { name: 'Company Lookup & Data', price: 'Free', highlight: false },
  { name: 'Filing History Viewer', price: 'Free', highlight: false },
  { name: 'VAT Number Validation', price: 'Free', highlight: false },
  { name: 'Shopify Data Import', price: 'Free', highlight: false },
  { name: 'Confirmation Statement (CS01)', price: '£14.99', highlight: true },
  { name: 'Annual Accounts (AA)', price: '£24.99', highlight: true },
  { name: 'VAT Return (MTD)', price: '£9.99', highlight: true },
  { name: 'Corporation Tax (CT600)', price: '£34.99', highlight: true },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b bg-white sticky top-0 z-50">
        <div className="container mx-auto flex h-16 items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
              <Building2 className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-gray-900">Tax Stride</span>
          </div>
          <nav className="hidden md:flex items-center gap-6 text-sm text-gray-600">
            <Link href="/companies/search" className="hover:text-gray-900">Company Search</Link>
            <Link href="#pricing" className="hover:text-gray-900">Pricing</Link>
            <Link href="#features" className="hover:text-gray-900">Features</Link>
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href="/auth/login"
              className="text-sm text-gray-600 hover:text-gray-900 font-medium"
            >
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
            >
              Get Started Free
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="gradient-brand py-20 text-white">
        <div className="container mx-auto text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1.5 text-sm mb-6">
            <Zap className="h-4 w-4" />
            <span>Free lookups · Pay only when you submit</span>
          </div>
          <h1 className="text-4xl md:text-6xl font-bold mb-6 leading-tight">
            UK Company Compliance<br />
            <span className="text-brand-200">Made Simple</span>
          </h1>
          <p className="text-xl text-brand-100 mb-10 max-w-2xl mx-auto">
            Search Companies House, manage VAT returns, file confirmation statements
            and annual accounts — all in one platform. Free data, pay only to submit.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/companies/search"
              className="flex items-center gap-2 rounded-lg bg-white text-brand-700 px-6 py-3 font-semibold hover:bg-brand-50 transition-colors"
            >
              <Search className="h-5 w-5" />
              Search Companies Free
            </Link>
            <Link
              href="/auth/register"
              className="flex items-center gap-2 rounded-lg border-2 border-white/30 px-6 py-3 font-semibold hover:bg-white/10 transition-colors"
            >
              Create Account
              <ArrowRight className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Free Search Bar */}
      <section className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto max-w-2xl text-center">
          <p className="text-sm text-gray-500 mb-4 font-medium uppercase tracking-wide">
            Free Company Search — No Account Required
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Search by company name or number..."
              className="flex-1 rounded-lg border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <Link
              href="/companies/search"
              className="rounded-lg bg-brand-600 px-6 py-3 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
            >
              Search
            </Link>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Powered by Companies House Public Data API
          </p>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20">
        <div className="container mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              Everything You Need for UK Compliance
            </h2>
            <p className="text-gray-600 max-w-xl mx-auto">
              From free company lookups to paid submissions — all in one place.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.title}
                  className="rounded-xl border bg-white p-6 card-hover"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50">
                      <Icon className="h-5 w-5 text-brand-600" />
                    </div>
                    {feature.free ? (
                      <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
                        Free
                      </span>
                    ) : (
                      <span className="rounded-full bg-brand-100 px-2.5 py-0.5 text-xs font-medium text-brand-700">
                        {feature.price}
                      </span>
                    )}
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-2">{feature.title}</h3>
                  <p className="text-sm text-gray-600">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 bg-gray-50">
        <div className="container mx-auto max-w-2xl">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              Simple, Transparent Pricing
            </h2>
            <p className="text-gray-600">
              No subscriptions. No hidden fees. Pay only when you submit.
            </p>
          </div>
          <div className="rounded-2xl border bg-white overflow-hidden shadow-sm">
            {pricingItems.map((item, i) => (
              <div
                key={item.name}
                className={`flex items-center justify-between px-6 py-4 ${
                  i < pricingItems.length - 1 ? 'border-b' : ''
                } ${item.highlight ? 'bg-brand-50' : ''}`}
              >
                <div className="flex items-center gap-3">
                  <CheckCircle
                    className={`h-4 w-4 ${
                      item.highlight ? 'text-brand-600' : 'text-green-500'
                    }`}
                  />
                  <span className="text-sm text-gray-700">{item.name}</span>
                </div>
                <span
                  className={`text-sm font-semibold ${
                    item.highlight ? 'text-brand-700' : 'text-green-600'
                  }`}
                >
                  {item.price}
                </span>
              </div>
            ))}
          </div>
          <p className="text-center text-xs text-gray-400 mt-4">
            All prices include VAT. Stripe & PayPal accepted.
          </p>
        </div>
      </section>

      {/* Integrations */}
      <section className="py-16 border-t">
        <div className="container mx-auto text-center">
          <p className="text-sm text-gray-500 mb-6 font-medium uppercase tracking-wide">
            Integrations
          </p>
          <div className="flex flex-wrap justify-center gap-8 items-center">
            {['Shopify', 'eBay (soon)', 'WooCommerce (soon)', 'Xero (soon)', 'QuickBooks (soon)'].map((name) => (
              <span key={name} className="text-gray-400 font-medium text-sm">
                {name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="gradient-brand py-16 text-white text-center">
        <div className="container mx-auto">
          <h2 className="text-3xl font-bold mb-4">Ready to Get Started?</h2>
          <p className="text-brand-100 mb-8 max-w-lg mx-auto">
            Create a free account and start managing your UK company compliance today.
          </p>
          <Link
            href="/auth/register"
            className="inline-flex items-center gap-2 rounded-lg bg-white text-brand-700 px-8 py-3 font-semibold hover:bg-brand-50 transition-colors"
          >
            Create Free Account
            <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8 bg-gray-900 text-gray-400">
        <div className="container mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-brand-400" />
            <span className="text-sm font-medium text-white">CompaniesHouse Tax Stride</span>
          </div>
          <p className="text-xs">
            © {new Date().getFullYear()} CompaniesHouse Tax Stride. Not affiliated with Companies House or HMRC.
          </p>
          <div className="flex gap-4 text-xs">
            <Link href="/privacy" className="hover:text-white">Privacy</Link>
            <Link href="/terms" className="hover:text-white">Terms</Link>
            <Link href="/docs" className="hover:text-white">API Docs</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}