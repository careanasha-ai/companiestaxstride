'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Building2, Eye, EyeOff, Loader2, CheckCircle } from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { getErrorMessage } from '@/lib/utils';
import { toast } from 'sonner';

const schema = z.object({
  full_name: z.string().min(2, 'Full name must be at least 2 characters'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirm_password: z.string(),
  tenant_name: z.string().min(2, 'Business name must be at least 2 characters'),
}).refine((data) => data.password === data.confirm_password, {
  message: "Passwords don't match",
  path: ['confirm_password'],
});

type FormData = z.infer<typeof schema>;

const benefits = [
  'Free company lookups & filing history',
  'VAT return management',
  'Shopify sales import',
  'Pay only when you submit',
];

export default function RegisterPage() {
  const router = useRouter();
  const { register: registerUser, isLoading } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      await registerUser({
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        tenant_name: data.tenant_name,
      });
      toast.success('Account created! Welcome to Tax Stride.');
      router.push('/dashboard');
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-4xl grid md:grid-cols-2 gap-8 items-start">
        {/* Left: Benefits */}
        <div className="hidden md:block pt-8">
          <Link href="/" className="inline-flex items-center gap-3 mb-8">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600">
              <Building2 className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">Tax Stride</span>
          </Link>
          <h2 className="text-2xl font-bold text-gray-900 mb-3">
            UK Compliance, Simplified
          </h2>
          <p className="text-gray-600 mb-8">
            Manage your Companies House filings, VAT returns, and integrations
            from one dashboard.
          </p>
          <ul className="space-y-4">
            {benefits.map((benefit) => (
              <li key={benefit} className="flex items-center gap-3">
                <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                <span className="text-sm text-gray-700">{benefit}</span>
              </li>
            ))}
          </ul>
          <div className="mt-8 rounded-xl bg-brand-50 border border-brand-100 p-4">
            <p className="text-sm font-medium text-brand-800">
              🎉 Free to get started
            </p>
            <p className="text-xs text-brand-600 mt-1">
              No credit card required. Pay only when you submit filings.
            </p>
          </div>
        </div>

        {/* Right: Form */}
        <div>
          <div className="text-center mb-6 md:hidden">
            <Link href="/" className="inline-flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600">
                <Building2 className="h-6 w-6 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">Tax Stride</span>
            </Link>
          </div>

          <div className="bg-white rounded-2xl border shadow-sm p-8">
            <h1 className="text-xl font-bold text-gray-900 mb-1">Create your account</h1>
            <p className="text-sm text-gray-600 mb-6">
              Already have an account?{' '}
              <Link href="/auth/login" className="text-brand-600 hover:text-brand-700 font-medium">
                Sign in
              </Link>
            </p>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {/* Full Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Full Name
                </label>
                <input
                  {...register('full_name')}
                  type="text"
                  placeholder="John Smith"
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
                {errors.full_name && (
                  <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>
                )}
              </div>

              {/* Business Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Business / Trading Name
                </label>
                <input
                  {...register('tenant_name')}
                  type="text"
                  placeholder="My Business Ltd"
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
                {errors.tenant_name && (
                  <p className="mt-1 text-xs text-red-600">{errors.tenant_name.message}</p>
                )}
              </div>

              {/* Email */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Email Address
                </label>
                <input
                  {...register('email')}
                  type="email"
                  placeholder="you@example.com"
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
                {errors.email && (
                  <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
                )}
              </div>

              {/* Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    {...register('password')}
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Min. 8 characters"
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
                )}
              </div>

              {/* Confirm Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Confirm Password
                </label>
                <input
                  {...register('confirm_password')}
                  type="password"
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
                {errors.confirm_password && (
                  <p className="mt-1 text-xs text-red-600">{errors.confirm_password.message}</p>
                )}
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mt-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  'Create Free Account'
                )}
              </button>

              <p className="text-xs text-gray-400 text-center">
                By creating an account, you agree to our{' '}
                <Link href="/terms" className="underline">Terms</Link> and{' '}
                <Link href="/privacy" className="underline">Privacy Policy</Link>.
              </p>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}