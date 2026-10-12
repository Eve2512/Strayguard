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

Until the first PyPI release, install it from GitHub instead:

```bash
pipx install git+https://github.com/Eve2512/Strayguard
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
  - repo: https://github.com/Eve2512/Strayguard
    rev: v0.1.0
    hooks:
      - id: strayguard
```

The pre-commit framework captures the output of its hooks, so strayguard cannot ask you questions there. It shows the warning and lets the commit through, as described in [GUI clients, CI and coding agents](#gui-clients-ci-and-coding-agents).


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

  debug_output.json   output dump          87%
  test_fix2.py        scratch / leftover   91%

  [u] unstage   [g] add to .gitignore   [k] keep and commit   [o] one by one
  > g

  ✓ Added 2 files to .gitignore and staged .gitignore.
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


### GUI clients, CI and coding agents

strayguard asks you a question only when its output goes straight to your terminal. GUI git clients, CI, coding agents and the pre-commit framework all capture the output, so there strayguard warns and lets the commit through:

```text
⚠ strayguard: 2 new files may not belong (not blocking)

  debug_output.json   output dump          87%
  test_fix2.py        scratch / leftover   91%

  To unstage them:
    git rm --cached -r -- debug_output.json test_fix2.py
```

To block the commit instead, set `STRAYGUARD_STRICT=1`, this is a good setting for coding-agent sessions.


### Files caught by a local rule

These files are never sent to Jev, so they show `rule` instead of a percentage:

```text
  .env.local           local only           rule
```

### When strayguard can't reach Jev

It prints one line, still runs its local rules, and lets the commit through:

```text
strayguard: no TYPESAFE_API_KEY set, so only the local rules ran.
strayguard: Jev did not answer in 5 s, so only the local rules ran.
```

## Settings

Everything is optional except the key.

| Variable | Default | What it does |
|---|---|---|
| `TYPESAFE_API_KEY` | none | **Required.** Your TypeSafe API key. |
| `STRAYGUARD=off` | `on` | Skip the check for one commit: `STRAYGUARD=off git commit ...` |
| `STRAYGUARD_STRICT=1` | `0` | Block the commit when strayguard can't ask you, such as in CI or with agents. |
| `STRAYGUARD_THRESHOLD` | `0.70` | How sure Jev must be before strayguard warns you. |
| `STRAYGUARD_MODEL` | `jev-latest` | Pin a version, for example `jev-1.13.0`, to keep answers stable. |
| `STRAYGUARD_NAMES_ONLY=1` | `0` | Send only file names and sizes, never content. |

You can also skip every hook for one commit with `git commit --no-verify`.

## Privacy

For each **new** text file, strayguard sends TypeSafe its path, its size, its first 40 lines (at most 2,000 characters) and the names of a few tracked files next to it.

It never sends:

- files that a local rule catches, such as `.env` files, keys and certificates
- binary files, or files larger than 1 MB
- any content at all when `STRAYGUARD_NAMES_ONLY=1` is set

TypeSafe says it does not train models on customer data. See its [legal page](https://docs.typesafe.ai/legal).

## Cost and speed

- A typical commit costs less than $0.0001.
- The check usually finishes in under a second.
- Each file's answer is cached by its content, so running the commit again is instant and free.

## Uninstall

```bash
strayguard uninstall
```

This removes the hook only if strayguard wrote it.

## Commands

| Command | What it does |
|---|---|
| `strayguard install` | Add the pre-commit hook to this repo |
| `strayguard uninstall` | Remove the hook |
| `strayguard check` | Run the check on staged new files (the hook runs this) |
| `strayguard --version` | Show the version |

## Development

Run the unit tests. They use no network and no API key:

```bash
uv run --no-project --with pytest pytest
```

GitHub Actions runs the same tests on Python 3.9 to 3.14 for each push to `main` and for each pull request.

## License

MIT. See [LICENSE](https://github.com/Eve2512/Strayguard/blob/main/LICENSE).

