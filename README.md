# 🏢 CompaniesHouse Tax Stride

A comprehensive, cloud-based UK compliance platform for Companies House filing, VAT submissions, and tax management. Built with Next.js, FastAPI, and PostgreSQL — deployed on Railway.

---

## 🚀 Features

### Free Tier (No Account Required)
- 🔍 Company lookup via Companies House API
- 📊 Filing history & accounts viewer
- 📋 VAT number validation
- 📈 Financial reports & data explorer

### Paid (Pay-Per-Submission)
- ✅ Confirmation Statement filing (CS01)
- ✅ Annual Accounts filing (AA)
- ✅ VAT Return submission (MTD-compliant)
- ✅ Corporation Tax (CT600) submission

### Integrations
- 🛒 Shopify — auto-import sales/VAT data
- 🛍️ eBay (coming soon)
- 🛒 WooCommerce (coming soon)
- 📊 Xero / QuickBooks (coming soon)

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router) + Tailwind CSS + shadcn/ui |
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 |
| Auth | JWT + bcrypt (multi-tenant) |
| Payments | Stripe + PayPal |
| Deployment | Railway |
| CI/CD | GitHub Actions |

---

## 📁 Project Structure

```
companiestaxstride/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/v1/endpoints/ # Route handlers
│   │   ├── core/             # Config, security, dependencies
│   │   ├── db/               # Models & migrations
│   │   ├── services/         # Business logic
│   │   ├── schemas/          # Pydantic models
│   │   └── utils/            # Helpers
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                 # Next.js application
│   ├── src/
│   │   ├── app/              # App Router pages
│   │   ├── components/       # Reusable UI components
│   │   ├── lib/              # API clients, utilities
│   │   ├── hooks/            # Custom React hooks
│   │   ├── types/            # TypeScript types
│   │   └── store/            # Zustand state management
│   ├── package.json
│   └── Dockerfile
├── deployment/
│   ├── railway/              # Railway config files
│   ├── docker/               # Docker compose
│   └── nginx/                # Nginx config
└── .github/workflows/        # CI/CD pipelines
```

---

## 🛠️ Local Development

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- Docker (optional)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Fill in your values
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
cp .env.local.example .env.local  # Fill in your values
npm run dev
```

### Full Stack with Docker
```bash
docker-compose up --build
```

---

## 🚂 Railway Deployment

1. Fork/clone this repo to your GitHub
2. Connect Railway to your GitHub repo
3. Add environment variables (see `.env.example`)
4. Railway auto-detects `railway.toml` and deploys both services

---

## 🔑 Environment Variables

See `backend/.env.example` and `frontend/.env.local.example` for all required variables.

Key variables:
- `COMPANIES_HOUSE_API_KEY` — from [developer.company-information.service.gov.uk](https://developer.company-information.service.gov.uk)
- `HMRC_CLIENT_ID` / `HMRC_CLIENT_SECRET` — from [HMRC Developer Hub](https://developer.service.hmrc.gov.uk)
- `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY`
- `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET`
- `SHOPIFY_API_KEY` / `SHOPIFY_API_SECRET`

---

## 📜 License

MIT License — see [LICENSE](LICENSE)

---

## 🤝 Contributing

Pull requests welcome. For major changes, please open an issue first.