'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  Search, Building2, MapPin, Calendar, Tag,
  ExternalLink, ChevronRight, Loader2, Info
} from 'lucide-react';
import { publicApi } from '@/lib/api';
import { formatDate, getCompanyStatusColor, formatCompanyNumber } from '@/lib/utils';
import { CompanySearchResult } from '@/types';

export default function CompanySearchPage() {
  const [query, setQuery] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['company-search', searchTerm],
    queryFn: () => publicApi.searchCompanies(searchTerm).then((r) => r.data),
    enabled: searchTerm.length >= 2,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length >= 2) setSearchTerm(query.trim());
  };

  const results: CompanySearchResult[] = data?.items || [];
  const total = data?.total_results || 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="gradient-brand py-12 text-white">
        <div className="container mx-auto max-w-3xl px-4">
          <div className="flex items-center gap-2 mb-2">
            <Link href="/" className="text-brand-200 hover:text-white text-sm">Home</Link>
            <ChevronRight className="h-4 w-4 text-brand-300" />
            <span className="text-sm">Company Search</span>
          </div>
          <h1 className="text-3xl font-bold mb-2">Company Search</h1>
          <p className="text-brand-100 mb-6">
            Search the Companies House register — completely free, no account required.
          </p>

          {/* Search Form */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by company name or number..."
                className="w-full rounded-xl border-0 pl-11 pr-4 py-3.5 text-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-white/50 shadow-sm"
              />
            </div>
            <button
              type="submit"
              disabled={query.length < 2}
              className="rounded-xl bg-white text-brand-700 px-6 py-3.5 text-sm font-semibold hover:bg-brand-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              Search
            </button>
          </form>
        </div>
      </div>

      {/* Results */}
      <div className="container mx-auto max-w-3xl px-4 py-8">
        {/* Free notice */}
        <div className="flex items-start gap-2 rounded-lg bg-blue-50 border border-blue-100 p-3 mb-6">
          <Info className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-blue-700">
            All company data is free to view. Create an account to add companies to your dashboard and file returns.
          </p>
        </div>

        {/* Loading */}
        {(isLoading || isFetching) && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
            <span className="ml-2 text-sm text-gray-500">Searching Companies House...</span>
          </div>
        )}

        {/* Results count */}
        {!isLoading && searchTerm && results.length > 0 && (
          <p className="text-sm text-gray-500 mb-4">
            Showing {results.length} of {total.toLocaleString()} results for &quot;{searchTerm}&quot;
          </p>
        )}

        {/* No results */}
        {!isLoading && searchTerm && results.length === 0 && (
          <div className="text-center py-12">
            <Building2 className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No companies found</p>
            <p className="text-sm text-gray-400 mt-1">
              Try searching by company number or a different name
            </p>
          </div>
        )}

        {/* Empty state */}
        {!searchTerm && (
          <div className="text-center py-12">
            <Search className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">Search for a company</p>
            <p className="text-sm text-gray-400 mt-1">
              Enter a company name or number above to get started
            </p>
          </div>
        )}

        {/* Results list */}
        {results.length > 0 && (
          <div className="space-y-3">
            {results.map((company) => (
              <Link
                key={company.company_number}
                href={`/companies/lookup/${company.company_number}`}
                className="block rounded-xl border bg-white p-5 card-hover"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-gray-900 truncate">
                        {company.company_name}
                      </h3>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getCompanyStatusColor(company.company_status)}`}
                      >
                        {company.company_status || 'Unknown'}
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
                      <span className="flex items-center gap-1 text-xs text-gray-500">
                        <Building2 className="h-3 w-3" />
                        {formatCompanyNumber(company.company_number)}
                      </span>
                      {company.date_of_creation && (
                        <span className="flex items-center gap-1 text-xs text-gray-500">
                          <Calendar className="h-3 w-3" />
                          Incorporated {formatDate(company.date_of_creation)}
                        </span>
                      )}
                      {company.registered_office_address?.postal_code && (
                        <span className="flex items-center gap-1 text-xs text-gray-500">
                          <MapPin className="h-3 w-3" />
                          {company.registered_office_address.postal_code}
                        </span>
                      )}
                    </div>

                    {company.sic_codes && company.sic_codes.length > 0 && (
                      <div className="flex items-center gap-1 mt-2 flex-wrap">
                        <Tag className="h-3 w-3 text-gray-400" />
                        {company.sic_codes.slice(0, 3).map((code) => (
                          <span
                            key={code}
                            className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600"
                          >
                            {code}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-brand-600 font-medium hidden sm:block">
                      View details
                    </span>
                    <ExternalLink className="h-4 w-4 text-gray-400" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}