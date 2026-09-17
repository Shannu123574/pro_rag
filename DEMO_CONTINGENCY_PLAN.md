# DEMO CONTINGENCY PLAN

### OpenAI Unavailable
Acknowledge this to the audience. The system will gracefully trigger the deterministic exact-match fallback. Present this as a core architectural feature.

### Render Startup Delay
Render Free/Starter tiers may sleep. Open the URL 5 minutes before the presentation to ensure the instances are warm.

### API Unavailable
Refresh the page. If persistent, check the Render dashboard for build/boot logs. Fall back to local Docker endpoint if necessary.

### Database Unavailable
Render PostgreSQL is managed. Ensure it has not been suspended.

### Network Problem
Proceed with the local Docker endpoint running on localhost.

### Browser Refresh
Refresh the browser. The architecture is stateless, so recovery is immediate.

### Model/Provider Timeout
The timeout will gracefully trigger the deterministic fallback engine.
