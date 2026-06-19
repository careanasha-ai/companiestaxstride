'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/store/auth';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Building2,
  FileText,
  Receipt,
  CreditCard,
  Settings,
  LogOut,
  ShoppingBag,
  BarChart3,
  AlertCircle,
  ChevronRight,
} from 'lucide-react';

const navigation = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    name: 'My Companies',
    href: '/companies',
    icon: Building2,
  },
  {
    name: 'Filings',
    href: '/filings',
    icon: FileText,
    children: [
      { name: 'All Filings', href: '/filings' },
      { name: 'Confirmation Statement', href: '/filings/confirmation-statement' },
      { name: 'Annual Accounts', href: '/filings/annual-accounts' },
    ],
  },
  {
    name: 'VAT',
    href: '/vat',
    icon: Receipt,
    children: [
      { name: 'VAT Returns', href: '/vat' },
      { name: 'Submit Return', href: '/vat/submit' },
      { name: 'Obligations', href: '/vat/obligations' },
    ],
  },
  {
    name: 'Reports',
    href: '/reports',
    icon: BarChart3,
  },
  {
    name: 'Integrations',
    href: '/settings/integrations',
    icon: ShoppingBag,
  },
  {
    name: 'Payments',
    href: '/payments',
    icon: CreditCard,
  },
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  return (
    <div className="flex h-full w-64 flex-col bg-gray-900 text-white">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-gray-700 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
          <Building2 className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-bold leading-tight">Tax Stride</p>
          <p className="text-xs text-gray-400">UK Compliance</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <ul className="space-y-1">
          {navigation.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.children?.some((c) => pathname === c.href));
            const Icon = item.icon;

            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-brand-600 text-white'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  )}
                >
                  <Icon className="h-4 w-4 flex-shrink-0" />
                  <span className="flex-1">{item.name}</span>
                  {item.children && (
                    <ChevronRight className="h-3 w-3 text-gray-500" />
                  )}
                </Link>
                {item.children && isActive && (
                  <ul className="mt-1 ml-7 space-y-1">
                    {item.children.map((child) => (
                      <li key={child.name}>
                        <Link
                          href={child.href}
                          className={cn(
                            'block rounded-md px-3 py-1.5 text-xs transition-colors',
                            pathname === child.href
                              ? 'text-white font-medium'
                              : 'text-gray-400 hover:text-white'
                          )}
                        >
                          {child.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Free tier notice */}
      <div className="mx-3 mb-3 rounded-lg bg-brand-900/50 border border-brand-700 p-3">
        <div className="flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-brand-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs font-medium text-brand-300">Free Lookups</p>
            <p className="text-xs text-gray-400 mt-0.5">
              All data lookups are free. Pay only when you submit.
            </p>
          </div>
        </div>
      </div>

      {/* User */}
      <div className="border-t border-gray-700 p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-xs font-bold">
            {user?.full_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">
              {user?.full_name || 'User'}
            </p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
          </div>
          <button
            onClick={logout}
            className="text-gray-400 hover:text-white transition-colors"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}