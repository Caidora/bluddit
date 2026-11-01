We are making a website called bluddit.com

This website will be used to support our guild, Bluds.

Core Mission: AI Enhanced efficient progression through classic dungeons and raids with a relaxed, positive mindset. We prioritize guild unity, cross-timezone camaraderie (AU/NZ/Perth), mutual aid in leveling and crafting, and zero-drama cooperation.

The current plan sheets can be found in https://docs.google.com/spreadsheets/d/1CtopiBvc1u_skUH29yOnmCAhc2qDYqVqrAiMTNWOgYE/edit?gid=19842026#gid=19842026

The sheets are a reference for guild needs and ideas. Build Bluddit as its own product, with workflows and a data model suited to the website rather than strict feature parity with spreadsheet tabs or formulas. The current release scope is described in [the feature plan](website-feature-plan.md).

Design direction:

- Bluddit should take inspiration from Reddit, with a goofy, lighthearted personality that fits the guild's relaxed, positive mindset.
- When adding new features, look for useful ways to bring in playful Reddit-inspired design and interactions, such as upvotes and downvotes on messages.
- Treat Reddit as inspiration rather than a requirement to copy its entire UI. Prioritize usability, accessibility, and clear guild workflows whenever a Reddit-style pattern would get in the way.

Tech stack:

- React Router framework with client-side rendering (CSR / SPA mode), not SSR
- fastapi
- nginx
- postgres
- Psycopg 3 (Python PostgreSQL driver), explicit parameterized SQL commands, no ORM
- CI/CD with github actions
- Authentication/ authorization with sessions.
- dockerise it all
- docker compose for running on server.
