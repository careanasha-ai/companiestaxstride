'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  Building2, FileText, Receipt, AlertTriangle,
  CheckCircle, Clock, ArrowRight, TrendingUp,
  Plus, RefreshCw
} from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { companiesApi, filingsApi } from '@/lib/api';
import { formatDate, getDeadlineColor, getDeadlineBgColor, getFilingTypeLabel, cn } from '@/lib/utils';
import { Deadline, Filing } from '@/types';

export default function DashboardPage() {
  const { user } = useAuthStore();

  const { data: companies = [] } = useQuery({
    queryKey: ['companies'],
    queryFn: () => companiesApi.listMy().then((r) => r.data),
  });

  const { data: deadlinesData } = useQuery({
    queryKey: ['deadlines'],
    queryFn: () => filingsApi.getDeadlines().then((r) => r.data),
  });

  const { data: recentFilings = [] } = useQuery({
    queryKey: ['filings', 'recent'],
    queryFn: () => filingsApi.list({ }).then((r) => r.data.slice(0, 5)),
  });

  const deadlines: Deadline[] = deadlinesData?.deadlines || [];
  const overdueCount = deadlines.filter((d) => d.is_overdue).length;
  const urgentCount = deadlines.filter((d) => d.is_urgent && !d.is_overdue).length;

  const stats = [
    {
      label: 'My Companies',
      value: companies.length,
      icon: Building2,
      color: 'text-brand-600',
      bg: 'bg-brand-50',
      href: '/companies',
    },
    {
      label: 'Upcoming Deadlines',
      value: deadlines.length,
      icon: Clock,
      color: 'text-yellow-600',
      bg: 'bg-yellow-50',
      href: '/filings',
    },
    {
      label: 'Overdue',
      value: overdueCount,
      icon: AlertTriangle,
      color: 'text-red-600',
      bg: 'bg-red-50',
      href: '/filings',
    },
    {
      label: 'Recent Filings',
      value: recentFilings.length,
      icon: FileText,
      color: 'text-green-600',
      bg: 'bg-green-50',
      href: '/filings',
    },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}! 👋
          </h1>
          <p className="text-gray-500 mt-1">
            Here&apos;s your UK compliance overview.
          </p>
        </div>
        <Link
          href="/companies"
          className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Company
        </Link>
      </div>

      {/* Overdue Alert */}
      {overdueCount > 0 && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-800">
              {overdueCount} overdue filing{overdueCount > 1 ? 's' : ''}
            </p>
            <p className="text-xs text-red-600 mt-0.5">
              Late filings may result in penalties from Companies House or HMRC.
            </p>
          </div>
          <Link
            href="/filings"
            className="ml-auto text-xs font-medium text-red-700 hover:text-red-800 flex items-center gap-1"
          >
            View <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Link
              key={stat.label}
              href={stat.href}
              className="rounded-xl border bg-white p-5 card-hover"
            >
              <div className={`inline-flex h-10 w-10 items-center justify-center rounded-lg ${stat.bg} mb-3`}>
                <Icon className={`h-5 w-5 ${stat.color}`} />
              </div>
              <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
              <p className="text-sm text-gray-500 mt-0.5">{stat.label}</p>
            </Link>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Upcoming Deadlines */}
        <div className="rounded-xl border bg-white">
          <div className="flex items-center justify-between p-5 border-b">
            <h2 className="font-semibold text-gray-900">Upcoming Deadlines</h2>
            <Link href="/filings" className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y">
            {deadlines.length === 0 ? (
              <div className="p-8 text-center">
                <CheckCircle className="h-8 w-8 text-green-400 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No upcoming deadlines</p>
              </div>
            ) : (
              deadlines.slice(0, 5).map((deadline, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-4 p-4 ${getDeadlineBgColor(deadline.days_remaining)}`}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {deadline.company_name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {getFilingTypeLabel(deadline.filing_type)} · Due {formatDate(deadline.due_date)}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className={`text-sm font-semibold ${getDeadlineColor(deadline.days_remaining)}`}>
                      {deadline.is_overdue
                        ? `${Math.abs(deadline.days_remaining)}d overdue`
                        : `${deadline.days_remaining}d left`}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Filings */}
        <div className="rounded-xl border bg-white">
          <div className="flex items-center justify-between p-5 border-b">
            <h2 className="font-semibold text-gray-900">Recent Filings</h2>
            <Link href="/filings" className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y">
            {recentFilings.length === 0 ? (
              <div className="p-8 text-center">
                <FileText className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500 mb-3">No filings yet</p>
                <Link
                  href="/filings/confirmation-statement"
                  className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                >
                  Create your first filing →
                </Link>
              </div>
            ) : (
              recentFilings.map((filing: Filing) => (
                <div key={filing.id} className="flex items-center gap-4 p-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      {getFilingTypeLabel(filing.filing_type)}
                    </p>
                    <p className="text-xs text-gray-500">
                      {filing.company_name} · {formatDate(filing.created_at)}
                    </p>
                  </div>
                  <span className={cn(
                    'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                    filing.status === 'accepted' ? 'bg-green-100 text-green-700' :
                    filing.status === 'submitted' ? 'bg-purple-100 text-purple-700' :
                    filing.status === 'paid' ? 'bg-blue-100 text-blue-700' :
                    filing.status === 'rejected' ? 'bg-red-100 text-red-700' :
                    'bg-gray-100 text-gray-700'
                  )}>
                    {filing.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              title: 'File Confirmation Statement',
              desc: 'CS01 · £14.99',
              href: '/filings/confirmation-statement',
              icon: FileText,
              color: 'text-brand-600',
              bg: 'bg-brand-50',
            },
            {
              title: 'File Annual Accounts',
              desc: 'AA · £24.99',
              href: '/filings/annual-accounts',
              icon: TrendingUp,
              color: 'text-purple-600',
              bg: 'bg-purple-50',
            },
            {
              title: 'Submit VAT Return',
              desc: 'MTD · £9.99',
              href: '/vat/submit',
              icon: Receipt,
              color: 'text-green-600',
              bg: 'bg-green-50',
            },
            {
              title: 'Search Companies',
              desc: 'Free lookup',
              href: '/companies/search',
              icon: Building2,
              color: 'text-orange-600',
              bg: 'bg-orange-50',
            },
          ].map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.title}
                href={action.href}
                className="rounded-xl border bg-white p-5 card-hover flex items-start gap-4"
              >
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${action.bg} flex-shrink-0`}>
                  <Icon className={`h-5 w-5 ${action.color}`} />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">{action.title}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{action.desc}</p>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}