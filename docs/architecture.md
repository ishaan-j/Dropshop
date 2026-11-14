# Architecture

The current design lives in [ARCHITECTURE.md](../ARCHITECTURE.md).

Layer rule that still holds: routers and the orchestrator call agents, repositories, and finance clients. Agents return data. They do not write the database. The browser does not receive secrets.

Harbor & Co replaced the earlier idea of demoing against invented Best Buy prices. Playwright targets only `/demo/retailer/claim`.
