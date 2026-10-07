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
