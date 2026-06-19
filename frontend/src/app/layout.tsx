import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Toaster } from 'sonner';
import { Providers } from '@/components/layout/Providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: {
    default: 'CompaniesHouse Tax Stride',
    template: '%s | CompaniesHouse Tax Stride',
  },
  description:
    'UK compliance platform for Companies House filing, VAT submissions, and tax management. Free lookups, pay only when you submit.',
  keywords: [
    'Companies House',
    'UK tax',
    'VAT return',
    'MTD',
    'confirmation statement',
    'annual accounts',
    'corporation tax',
    'CT600',
    'HMRC',
  ],
  authors: [{ name: 'CompaniesHouse Tax Stride' }],
  openGraph: {
    title: 'CompaniesHouse Tax Stride',
    description: 'UK compliance platform — free lookups, pay only when you submit.',
    type: 'website',
    locale: 'en_GB',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          {children}
          <Toaster
            position="top-right"
            richColors
            closeButton
            toastOptions={{
              duration: 4000,
            }}
          />
        </Providers>
      </body>
    </html>
  );
}