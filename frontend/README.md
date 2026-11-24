# Smart Roster frontend

React, Vite, TypeScript and Tailwind foundation for the Smart Roster API.

## Run locally

```sh
npm install
cp .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` to the backend API root (defaults to `http://localhost:8000/api/v1`). The frontend reads health/readiness, master-data lists and saved rosters from the API. Generation reports scheduling conflicts as a business outcome using the response diagnostics.

## Checks

```sh
npm test
npm run typecheck
npm run build
```

The seven navigation sections are the initial product shell. Full master-data editing and monthly roster views are intentionally left for later tasks.
