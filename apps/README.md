# SFRFR cabinets

Next.js apps for authenticated users:

| App | Path | Public URL (planned) | Local port |
|-----|------|----------------------|------------|
| Client | `apps/cabinet` | https://cabinet.taxi-doroga-dobra.ru | 3001 |
| Staff | `apps/admin` | https://admin.taxi-doroga-dobra.ru | 3002 |

Both call FastAPI `/api/portal/*` with Supabase access token (`Authorization: Bearer …`).

## Local

```powershell
cd apps/cabinet
copy .env.example .env
npm install
npm run dev -- --port 3001
```

```powershell
cd apps/admin
copy .env.example .env
npm install
npm run dev -- --port 3002
```

Do not put `SUPABASE_SERVICE_ROLE_KEY` in these apps.
