# Next Steps: Push to GitHub and Start Using

Your engineering home repo is **ready to go**! Here's what to do next.

---

## ✅ What's Already Done

- ✅ Git initialized with initial commit
- ✅ All files organized and committed
- ✅ Templates extracted (Python API + Node service)
- ✅ Sandboxie kit moved to `infra/sandboxie/`
- ✅ Cursor rules configured (`.cursor/rules/write-notes.mdc`)
- ✅ GitHub templates added (PR, issues, CODEOWNERS)
- ✅ Decision documentation template created
- ✅ Multi-root workspace file created

---

## 🚀 Step 1: Create GitHub Repository

**Option A: Via GitHub Web UI**
1. Go to https://github.com/new
2. Name: `engineering-home` (or `dev-home`)
3. Visibility: **Public** (recommended) or Private
4. **DO NOT** initialize with README, .gitignore, or license (you already have these)
5. Click "Create repository"
6. Copy the repository URL

**Option B: Via GitHub CLI**
```powershell
gh repo create engineering-home --public --source=. --remote=origin --push
```

---

## 🚀 Step 2: Push to GitHub (Manual Method)

If you created the repo via web UI:

```powershell
# Add the remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/engineering-home.git

# Push to GitHub
git push -u origin main
```

**Verify:**
```powershell
git remote -v
```

---

## 🚀 Step 3: Set Up Branch Protection

**On GitHub:**
1. Go to your repo → Settings → Branches
2. Add branch protection rule for `main`:
   - ☑ Require a pull request before merging
   - ☑ Require status checks to pass before merging (when you add CI)
   - ☑ Include administrators (if you want to follow your own rules)
3. Save changes

---

## 🚀 Step 4: Update CODEOWNERS

Edit `.github/CODEOWNERS` and replace `YOUR_GITHUB_USERNAME` with your actual GitHub username:

```bash
# Global fallback
* @your-actual-username
```

Then commit and push:
```powershell
git add .github/CODEOWNERS
git commit -m "chore: update CODEOWNERS with actual username"
git push
```

---

## 🎯 Step 5: Try Bootstrapping a New Project

**Test the Python API template:**

```powershell
# Bootstrap a new project
Copy-Item -Recurse -Force C:\dev\templates\starter-python-api C:\dev\apps\test-api
cd C:\dev\apps\test-api

# Initialize as separate repo
git init
git add .
git commit -m "feat: bootstrap from engineering-home template"

# Run it locally
cp .env.example .env
docker compose up --build
```

Visit http://localhost:8000 to see it running!

**Clean up test:**
```powershell
cd C:\dev
Remove-Item -Recurse -Force C:\dev\apps\test-api
```

---

## 🎯 Step 6: Set Up Workspace in Cursor

**Open the workspace file:**
```powershell
cursor C:\dev\engineering-home.code-workspace
```

Or in Cursor: File → Open Workspace from File → Select `engineering-home.code-workspace`

**To work on both home + a project:**
Edit `engineering-home.code-workspace` and add your app folder:
```json
{
  "folders": [
    { "path": ".", "name": "🏠 Engineering Home" },
    { "path": "../apps/my-api", "name": "📦 My API" }
  ]
}
```

---

## 📁 Your Polyrepo Structure

After creating some projects:

```
C:\dev\
├── engineering-home\        ← This repo (pushed to GitHub)
│   ├── docs\
│   ├── templates\
│   ├── infra\
│   └── .cursor\
├── apps\
│   ├── user-service\        ← Separate repo
│   ├── order-api\           ← Separate repo
│   └── ...
└── libs\
    ├── auth-sdk\            ← Separate repo
    └── ...
```

**Each app/lib is its own repo** with its own remote on GitHub.

---

## 🔧 Optional: Add CI/CD to Engineering Home

Create `.github/workflows/validate-templates.yml`:

```yaml
name: Validate Templates
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: List templates
        run: ls -la templates/
      - name: Validate markdown
        run: find . -name "*.md" -exec echo "✓ {}" \;
```

Commit and push:
```powershell
git add .github/workflows/validate-templates.yml
git commit -m "ci: add template validation workflow"
git push
```

---

## 📚 Quick Reference

**Core files:**
- `README.md` – Overview and quick start
- `docs/README.md` – Knowledge base structure
- `templates/README.md` – Template usage guide
- `infra/README.md` – Infrastructure overview
- `.cursor/rules/write-notes.mdc` – Documentation standards

**Decision template:**
- `docs/architecture/decisions/YYYY-MM-DD_template.md`

**Templates:**
- `templates/starter-python-api/` – FastAPI + PostgreSQL
- `templates/starter-node-service/` – Node + TypeScript + PostgreSQL

**Infrastructure:**
- `infra/sandboxie/` – Sandboxie Plus configurations

---

## 🎉 You're Done!

Your engineering home is ready. Now when you:
- Start a new project → copy from `templates/`
- Make a decision → add to `docs/architecture/decisions/`
- Save AI output → add to `docs/gpt-summaries/_inbox/`, organize later
- Need infra → check `infra/`

**Open Cursor with this repo anytime you need the templates or docs.**

---

**Questions?** Check:
- `README.md` for overview
- `docs/QUICK_START.md` for quick reference
- `docs/architecture/decisions/2025-10-26_setup-engineering-home.md` for the full decision record


