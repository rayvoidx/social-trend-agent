# Social Trend Agent — Web UI

React 19 + TypeScript frontend for the Social Trend Agent dashboard.

## Tech Stack

- **React 19** with TypeScript
- **Vite** for bundling and HMR
- **Tailwind CSS** for styling
- **Recharts** for data visualization

## Development

```bash
npm install
npm run dev        # Start dev server on http://localhost:5173
npm run build      # Production build
npm run lint       # ESLint check
npm run typecheck  # TypeScript type checking
```

## Project Structure

```
src/
├── api/           # API client and types
├── components/    # React components (Dashboard, ResultCard, TaskProgress)
├── hooks/         # Custom hooks (useTaskStream)
├── types/         # TypeScript type definitions
├── App.tsx        # Root component
└── main.tsx       # Entry point
```

## Environment Variables

| Variable       | Description          | Default                 |
| -------------- | -------------------- | ----------------------- |
| `VITE_API_URL` | Backend API base URL | `/` (proxied via nginx) |

## Docker

The web UI runs in Docker via nginx reverse proxy:

```bash
docker compose up web
```

This serves the built frontend on port 5173 and proxies `/api` requests to the backend.
