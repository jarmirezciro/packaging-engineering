# Installing KolliPack Codex documentation (v2)

This v2 adds Multi-product Container Selection and Multi-product Bag Selection to the mandatory shared-consumer contract, and adds selective documentation loading guidance to control token use.

This package is designed to be extracted at the repository root, normally:

```powershell
C:\PackagingEngineering
```

After extraction, the repository should contain:

```text
C:\PackagingEngineering\AGENTS.md
C:\PackagingEngineering\docs\README.md
C:\PackagingEngineering\docs\...
```

## Safe installation

1. Create a checkpoint or confirm a clean Git state:

```powershell
git status
git add .
git commit -m "Checkpoint before Codex documentation"
```

2. Extract the ZIP into the repository root.
3. Review the new files:

```powershell
git status
git diff -- AGENTS.md docs
```

4. Commit only after reviewing the content:

```powershell
git add AGENTS.md docs
git commit -m "Add KolliPack agent and architecture documentation"
```

The documentation intentionally does not modify application code.
