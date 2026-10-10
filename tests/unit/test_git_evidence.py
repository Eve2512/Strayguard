import subprocess

from conftest import staged_paths
from strayguard import evidence, git

def test_new_files_only_status_a(repo, stage):
  stage ({"src/old.py": "x = 1\n"})
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

