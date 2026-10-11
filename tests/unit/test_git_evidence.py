import subprocess

from conftest import staged_paths
from strayguard import evidence, git


def test_new_files_only_status_a(repo, stage):
    stage({"src/old.py": "x = 1\n"})
    subprocess.run(["git", "commit", "-qm", "more"], check=True)
    subprocess.run(["git", "mv", "src/old.py", "src/new.py"], check=True)  # rename: skipped
    (repo / "README.md").write_text("changed\n")                           # modified: skipped
    stage({"my notes é.md": "todo\n"})
    assert [f.path for f in git.new_files()] == ["my notes é.md"]


def test_no_new_files(repo):  # T-01 (git part)
    assert git.new_files() == []


def test_folder_roll_up(repo, stage):  # T-04
    stage({f"dist/chunk{i}.js": f"var a{i};\n" for i in range(11)})
    items, total, _ = evidence.build_items(git.new_files())
    assert total == 1
    assert items[0].path == "dist/" and items[0].is_folder
    assert items[0].evidence["new_files"] == 11
    assert len(items[0].blob_ids) == 11


def test_ten_files_are_not_rolled_up(repo, stage):
    stage({f"dist/chunk{i}.js": f"var a{i};\n" for i in range(10)})
    items, total, _ = evidence.build_items(git.new_files())
    assert total == 10 and not any(i.is_folder for i in items)


def test_folder_with_tracked_files_is_not_rolled_up(repo, stage):
    stage({"src/app.py": "x\n"})
    subprocess.run(["git", "commit", "-qm", "src"], check=True)
    stage({f"src/m{i}.py": f"x{i}\n" for i in range(11)})
    items, _, _ = evidence.build_items(git.new_files())
    assert not any(i.is_folder for i in items)


def test_secret_content_is_never_read(repo, stage):  # T-02
    stage({".env.local": "SECRET=abc\n"})
    items, _, _ = evidence.build_items(git.new_files())
    assert "head" not in items[0].evidence


def test_names_only(repo, stage, monkeypatch):  # SG-36
    monkeypatch.setenv("STRAYGUARD_NAMES_ONLY", "1")
    stage({"notes.txt": "private\n"})
    items, _, _ = evidence.build_items(git.new_files())
    assert "head" not in items[0].evidence and "binary" not in items[0].evidence


def test_head_binary_and_large(repo, stage):
    stage({"long.py": "".join(f"line {i}\n" for i in range(100)),
           "logo.png": b"\x89PNG\0\0data",
           "big.csv": "a,b\n" * 300_000})
    items = {i.path: i.evidence for i in evidence.build_items(git.new_files())[0]}
    assert items["long.py"]["head"].count("\n") == 39  # 40 lines
    assert items["logo.png"]["binary"] is True and "head" not in items["logo.png"]
    assert items["big.csv"]["size_bytes"] == 1_200_000 and "head" not in items["big.csv"]


def test_repo_context(repo, stage):
    stage({"src/app.py": "x\n"})
    subprocess.run(["git", "commit", "-qm", "src"], check=True)
    stage({"src/scratch.py": "y\n"})
    items, _, top = evidence.build_items(git.new_files())
    assert top == ["README.md", "src/"]
    assert items[0].evidence["same_folder"] == ["app.py"]


def test_unstage_keeps_file_on_disk(repo, stage):  # T-07 (git part)
    stage({"scratch.py": "x\n"})
    (repo / "scratch.py").write_text("changed after git add\n")
    git.unstage(["scratch.py"])
    assert staged_paths() == []
    assert (repo / "scratch.py").exists()


def test_gitignore_lines_escaped_and_not_duplicated(repo, stage):  # T-08 (git part)
    stage({"a[1]*.py": "x\n", "dist/x.js": "y\n"})
    items = {i.path: i for i in evidence.build_items(git.new_files())[0]}
    (repo / ".gitignore").write_text("*.log")  # no newline at the end
    git.add_to_gitignore([items["a[1]*.py"], items["dist/x.js"]])
    git.add_to_gitignore([items["a[1]*.py"]])
    assert (repo / ".gitignore").read_text() == "*.log\n/a\\[1]\\*.py\n/dist/x.js\n"
    assert ".gitignore" in staged_paths()


def test_hooks_dir_respects_hooks_path(repo):
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], check=True)
    assert git.hooks_dir() == (repo / ".githooks").resolve()
