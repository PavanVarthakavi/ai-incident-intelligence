# Frontend

Web interface for the AI Incident Intelligence Platform: an incident list, each incident as a
report whose claims link to the evidence they cite, and a form for new incidents.

```bash
npm install
npm run dev      # http://localhost:5173; proxies /v1 to the backend on 127.0.0.1:8000
npm test         # component tests
npm run e2e      # end-to-end tests against the backend with the offline model
```

See [`../docs/frontend.md`](../docs/frontend.md) for screens, testing, and known limitations,
and [`../docs/DESIGN.md`](../docs/DESIGN.md) for the design system.
