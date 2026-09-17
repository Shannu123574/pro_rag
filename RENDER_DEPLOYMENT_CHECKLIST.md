# RENDER DEPLOYMENT CHECKLIST

### GitHub
- [ ] repository connected
- [ ] correct branch selected
- [ ] expected commit matched

### Render
- [ ] Blueprint recognized
- [ ] frontend service created
- [ ] API service created
- [ ] PostgreSQL created
- [ ] environment variables configured
- [ ] OpenAI key injected securely

### Network
- [ ] HTTPS active
- [ ] frontend connects to API
- [ ] API connects to private PostgreSQL
- [ ] no public PostgreSQL port exposed

### Application
- [ ] health passes
- [ ] readiness passes
- [ ] ingestion works
- [ ] query works
- [ ] citations validate
- [ ] abstention triggers correctly
- [ ] contradiction halts generation
- [ ] fallback mechanism engages

### Security
- [ ] no secrets committed in Git
- [ ] CORS limits enforced
- [ ] trusted hosts configured
- [ ] input validation active
- [ ] prompt-injection safely blocked
