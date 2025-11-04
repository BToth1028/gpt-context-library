# GPT Context Library

A structured system for organizing GPT/ChatGPT consultation requests with complete context, code, and analysis.

## 🎯 What is This?

This repository demonstrates a **3-tier versioned folder structure** for managing complex technical consultations with AI assistants like ChatGPT. Instead of messy chat histories, this system organizes:

- Complete problem context and goals
- All relevant code files
- Configuration files
- Error logs and screenshots
- Solution iterations and versions

## 📁 Structure

```
gpt/
├── _admin/                       # Templates and documentation
│   ├── _README/                  # System guide (you are here)
│   └── template/                 # Reusable templates
│
├── systems/                      # Tier 1: System architecture topics
│   └── context-management/       # Tier 2: Subcategory
│       └── project-context-os/   # Tier 3: Specific topic
│           ├── README.md         # Topic overview + version history
│           └── YYMMDD-HHMM_VXX/  # Versioned consultation
│               ├── request/      # Problem briefing
│               ├── code/         # Source files
│               ├── config/       # Configurations
│               ├── logs/         # Error logs
│               ├── docs/         # Screenshots
│               └── zip/          # Flattened for easy sharing
│
└── operations/                   # Tier 1: DevOps topics
    └── windows-integration/      # Tier 2: Subcategory
        └── sandboxie/            # Tier 3: Specific topic
```

## 🚀 How to Use This System

### For Your Own Projects

1. **Copy the template**:
   ```bash
   cp -r _admin/template/VERSION_TEMPLATE your-topic/YYMMDD-HHMM_V01
   ```

2. **Fill in the briefing**:
   - Edit `request/BRIEFING.txt` with complete context
   - Include: problem, goal, current status, errors

3. **Add your files**:
   - Code → `code/`
   - Configs → `config/`
   - Logs → `logs/`
   - Screenshots → `docs/`

4. **Flatten for GPT**:
   - Copy all files to `zip/` (no subfolders)
   - Makes it easy to paste into ChatGPT

5. **Document the solution**:
   - Update Tier 3 README with results
   - Link to related resources

### Browsing This Repository

Each **Tier 3 folder** represents a specific topic with:
- **README.md** - Topic overview and version history
- **Versioned folders** - Each consultation session

Example path:
```
systems/context-management/project-context-os/251027-1400_V04/
```
- `251027` = Oct 27, 2025
- `1400` = 2:00 PM (24-hour format)
- `V04` = 4th version/iteration on this topic

## 🎓 Why This Works

### Traditional Approach (❌):
- Scattered chat histories
- Lost context between sessions
- Can't track solution evolution
- Hard to share with team

### This System (✅):
- **Complete context** - Everything needed in one place
- **Versioned** - Track how solutions evolve
- **Searchable** - Find past solutions quickly
- **Shareable** - Easy to reference via GitHub URL
- **Reusable** - Templates speed up future requests

## 📝 Folder Guidelines

### Tier 1 (High-Level Categories)
- `systems/` - Architecture, design patterns
- `operations/` - DevOps, infrastructure
- `automation/` - Scripts, workflows

### Tier 2 (Subcategories)
- Groups related topics
- Examples: `context-management/`, `windows-integration/`

### Tier 3 (Specific Topics)
- Single problem/feature/implementation
- Has README + version folders

## 🔧 Integration Tips

### Reference in ChatGPT
```
"I'm working on a problem similar to this one:
https://github.com/your-username/gpt-context-library/tree/main/systems/context-management/project-context-os/251027-1400_V04

Can you review my approach?"
```

### Use as Team Knowledge Base
- Team members can browse past solutions
- Learn from previous iterations
- See what worked and what didn't

### Automate with Cursor
If you use Cursor IDE, add this to `.cursor/rules/project-standards.mdc`:
```markdown
When user says "Give me a GPT summary":
1. Check existing tiers in docs/gpt/
2. Create version folder: YYMMDD-HHMM_VXX
3. Generate complete BRIEFING.txt
4. Copy all relevant files
5. Flatten to zip/ folder
```

## 📚 Example Topics

Browse real examples:
- **[Project Context OS](systems/context-management/project-context-os/)** - 4-portal engineering workspace
- **[Sandboxie Integration](operations/windows-integration/sandboxie/)** - Windows development isolation

## 🤝 Contributing

This is my personal GPT consultation library, but feel free to:
- Fork and adapt the structure for your needs
- Open issues if you have suggestions
- Share your own GPT summary system

## 📄 License

MIT License - Use this system however you want!

## 🔗 Related Resources

- **Template Usage Guide**: [_admin/template/USAGE.md](_admin/template/USAGE.md)
- **Tier README Templates**: [_admin/template/](_admin/template/)
- **My Engineering Workspace**: *(link to your main portfolio/blog)*

---

**Last Updated**: November 4, 2025

**Note**: This is a living document. As I refine my GPT consultation process, this structure will evolve.
