from pathlib import Path

from smith.tools.duplicates import FindDuplicateFilesTool
from smith.tools.organize import OrganizeDownloadsTool, _categorize


def test_find_duplicates(tmp_path):
    (tmp_path / "a.txt").write_text("same content")
    (tmp_path / "b.txt").write_text("same content")
    (tmp_path / "c.txt").write_text("unique")

    tool = FindDuplicateFilesTool()
    result = tool.execute(path=str(tmp_path))

    assert result.success
    assert "Group 1" in result.output
    assert "a.txt" in result.output
    assert "b.txt" in result.output


def test_find_duplicates_empty(tmp_path):
    tool = FindDuplicateFilesTool()
    result = tool.execute(path=str(tmp_path))
    assert result.success
    assert "No duplicates found" in result.output


def test_find_duplicates_min_size(tmp_path):
    (tmp_path / "small.txt").write_text("x")
    dup1 = tmp_path / "d1.bin"
    dup2 = tmp_path / "d2.bin"
    dup1.write_bytes(b"x" * 100)
    dup2.write_bytes(b"x" * 100)

    tool = FindDuplicateFilesTool()
    result = tool.execute(path=str(tmp_path), min_size=50)
    assert result.success
    assert "Group 1" in result.output
    assert "small.txt" not in result.output


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
    assert "dry-run" in result.output
    assert (tmp_path / "readme.md").exists()
    assert (tmp_path / "photo.png").exists()


def test_organize_moves_files(tmp_path):
    (tmp_path / "readme.md").write_text("# hi")

    tool = OrganizeDownloadsTool()
    result = tool.execute(path=str(tmp_path), dry_run=False)

    assert result.success
    assert (tmp_path / "Documents" / "readme.md").exists()
    assert not (tmp_path / "readme.md").exists()


def test_organize_collision_rename(tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    (docs / "file.txt").write_text("existing")
    (tmp_path / "file.txt").write_text("new")

    tool = OrganizeDownloadsTool()
    result = tool.execute(path=str(tmp_path), dry_run=False)

    assert result.success
    assert (docs / "file_1.txt").exists()
