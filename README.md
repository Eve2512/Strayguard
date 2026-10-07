# Strayguard
Catch files that don't belong before you commit them. A git pre-commit hook that asks TypeSafe Jev whether each new file belongs in your repo. It catches scratch scripts, debug dumps, build output and local config before they land. Takes under a second, costs a fraction of a cent, needs no config.


### Why

```git add .``` adds everything. Sometimes that includes:

- ```test_fix2.py```, a throwaway script
- ```debug_output.json```, which you dumped while chasing a bug
- ```notes-to-self.md```
- ```data_export.csv``` with real customer rows
- ```.env.local``` with your own settings
- a whole ```dist/``` folder

Coding agents make this worse, they create helper scripts and scratch files and often don't clean them up.
Whatever coding tool you use most likely miss most of these files:

| Tool | Catches | Misses |
|---|---|---|
| ```.gitignore``` | Names you listed in advance | Every name you didn't think of |
| Secret scanners | API keys and tokens | Junk scripts, data dumps, notes |
| Large-file checks | Big files | Small junk files |
| **strayguard** | **Files that don't look like part of the project** | Changes to files git already tracks |


### How it works

1. You run ```git commit```.
2. strayguard looks only at files that are **new** in this commit.
3. A few local rules run first, such as ```.env``` and ```.DS_Store```. Files they match are never sent anywhere.
4. For the other files, Jev picks one category: **belongs**, **scratch / leftover**, **output dump**, **build output** or **local only**.
5. If Jev is at least 70% sure a file doesn't belong, strayguard shows it to you.
6. If everything belongs, you see nothing.

Jev never writes text(not good for that anyways) It only picks a category and returns a probability. The same file always gets the same answer, because strayguard caches the result.

### Install

You need Python 3.9+ and a [TypeSafe API key](https://console.typesafe.ai/keys).

```bash
pipx install strayguard
```

```bash
export TYPESAFE_API_KEY=your-key
```

Then, inside your repo:

```bash
strayguard install
```

```text
✓ strayguard installed in .git/hooks/pre-commit
```

That's it, there's no config file


### With the pre-commit framework

Add this to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/<you>/strayguard
    rev: v1.0.0
    hooks:
      - id: strayguard
```


## What you'll see

### Everything belongs

Nothing, your commit goes through as normal.

```text
$ git commit -m "add login page"
[main 4f2a91c] add login page
 3 files changed, 120 insertions(+)
```

### Something looks wrong

```text
$ git commit -m "add login page"

⚠ strayguard: 2 new files look like they don't belong

  test_fix2.py         scratch / leftover   91%
  debug_output.json    output dump          87%

  [u] unstage   [g] add to .gitignore   [k] keep and commit   [o] one by one
  > g

  ✓ Added 2 lines to .gitignore and staged .gitignore.
  ✓ Unstaged 2 files. They are still on your disk.

  Commit stopped so you can check. Run git commit again.
```

| Key | What it does |
|---|---|
| `u` | Takes the files out of this commit. They stay on your disk. |
| `g` | Adds the files to `.gitignore` so this never happens again, and takes them out of this commit. |
| `k` | Commits the files anyway. strayguard won't ask about them again. |
| `o` | Lets you choose `u`, `g` or `k` for each file. |
| Enter | Same as `k`. |

strayguard **never deletes files**. It stops the commit only if it changed something for you, so you can check before you commit again.
