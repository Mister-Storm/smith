from pathlib import Path

from smith.tools.duplicates import FindDuplicateFilesTool
from smith.tools.fs_utils import (
    format_bytes,
    should_skip_context_path,
    should_skip_path,
)
from smith.tools.organize import OrganizeDownloadsTool, _categorize


def test_should_skip_path(tmp_path):
    git_dir = tmp_path / ".git" / "config"
    git_dir.parent.mkdir()
    git_dir.write_text("ref")
    assert should_skip_path(git_dir, tmp_path) is True

    normal = tmp_path / "src" / "main.kt"
    normal.parent.mkdir()
    normal.write_text("x")
    assert should_skip_path(normal, tmp_path) is False


def test_should_skip_context_path(tmp_path):
    docs_file = tmp_path / "docs" / "guide.md"
    docs_file.parent.mkdir(parents=True)
    docs_file.write_text("# guide")
    assert should_skip_context_path(docs_file, tmp_path) is True

    test_file = tmp_path / "tests" / "test_app.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_x(): pass")
    assert should_skip_context_path(test_file, tmp_path) is True

    src_file = tmp_path / "src" / "app.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("print('hi')")
    assert should_skip_context_path(src_file, tmp_path) is False


def test_format_bytes():
    assert format_bytes(500) == "500 B"
    assert "KB" in format_bytes(2048)
    assert "MB" in format_bytes(2 * 1024 * 1024)


def test_find_duplicates(tmp_path):
    (tmp_path / "a.txt").write_text("same content")
    (tmp_path / "b.txt").write_text("same content")
    (tmp_path / "c.txt").write_text("unique")

    tool = FindDuplicateFilesTool()
    result = tool.execute(path=str(tmp_path))

    assert result.success
    assert "Group 1" in result.message
    assert result.metadata["duplicate_groups"] == 1
    assert "recoverable" in result.message.lower() or "recoverable" in result.message


def test_find_duplicates_empty(tmp_path):
    tool = FindDuplicateFilesTool()
    result = tool.execute(path=str(tmp_path))
    assert result.success
    assert "No duplicates found" in result.message


def test_find_duplicates_min_size(tmp_path):
    (tmp_path / "small.txt").write_text("x")
    dup1 = tmp_path / "d1.bin"
    dup2 = tmp_path / "d2.bin"
    dup1.write_bytes(b"x" * 100)
    dup2.write_bytes(b"x" * 100)

    tool = FindDuplicateFilesTool()
    result = tool.execute(path=str(tmp_path), min_size=50)
    assert result.success
    assert "Group 1" in result.message
    assert "small.txt" not in result.message


def test_find_duplicates_invalid_path(tmp_path):
    tool = FindDuplicateFilesTool()
    result = tool.execute(path=str(tmp_path / "missing"))
    assert not result.success


def test_categorize():
    assert _categorize(Path("doc.pdf")) == "Documents"
    assert _categorize(Path("photo.jpg")) == "Images"
    assert _categorize(Path("main.kt")) == "Code"
    assert _categorize(Path("unknown.xyz")) == "Misc"


def test_organize_dry_run(tmp_path):
    (tmp_path / "readme.md").write_text("# hi")
    (tmp_path / "photo.png").write_bytes(b"\x89PNG")

    tool = OrganizeDownloadsTool()
    result = tool.execute(path=str(tmp_path), dry_run=True)

    assert result.success
    assert "dry-run" in result.message
    assert "Summary:" in result.message
    assert result.metadata["categories"]["Documents"] == 1


def test_organize_moves_files(tmp_path):
    (tmp_path / "readme.md").write_text("# hi")

    tool = OrganizeDownloadsTool()
    result = tool.execute(path=str(tmp_path), dry_run=False)

    assert result.success
    assert (tmp_path / "Documents" / "readme.md").exists()
    assert result.metadata["files_moved"] == 1


def test_organize_skips_category_folder(tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    (docs / "file.pdf").write_bytes(b"%PDF")

    tool = OrganizeDownloadsTool()
    result = tool.execute(path=str(docs), dry_run=True)

    assert result.success
    assert "Skipping" in result.message


def test_organize_collision_rename(tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    (docs / "file.txt").write_text("existing")
    (tmp_path / "file.txt").write_text("new")

    tool = OrganizeDownloadsTool()
    result = tool.execute(path=str(tmp_path), dry_run=False)

    assert result.success
    assert (docs / "file_1.txt").exists()
