from types import SimpleNamespace

import pytest

from app import (
    FILE_STATUS_PENDING,
    FILE_STATUS_VOID,
    checkout_error,
    folder_file_name_taken,
    normalize_create_filename,
    normalize_rename_filename,
    validate_upload_filename,
)
from tests.conftest import unique_name


class TestValidateUpload:
    @pytest.mark.parametrize(
        "name,ok",
        [
            ("a.docx", True),
            ("a.xlsx", True),
            ("a.txt", True),
            ("a.zip", True),
            ("a.pdf", False),
        ],
    )
    def test_extensions(self, name, ok):
        passed, _ = validate_upload_filename(name)
        assert passed is ok


class TestNormalizeCreateFilename:
    def test_adds_extension(self):
        display, stored = normalize_create_filename("需求说明", "word")
        assert display == "需求说明.docx"
        assert stored.endswith("docx")

    def test_invalid_kind(self):
        display, err = normalize_create_filename("x", "pdf")
        assert display is None
        assert "不支持" in err

    def test_name_too_long(self):
        display, err = normalize_create_filename("x" * 121, "txt")
        assert display is None
        assert "120" in err


class TestNormalizeRename:
    def test_keeps_extension(self):
        f = SimpleNamespace(name="旧名称.docx")
        new_name, err = normalize_rename_filename("新标题", f)
        assert err is None
        assert new_name == "新标题.docx"


class TestCheckoutError:
    def test_void_blocked(self, app_ctx):
        f = SimpleNamespace(status=FILE_STATUS_VOID, checked_out_by=None)
        assert "作废" in checkout_error(f)

    def test_pending_blocked(self, app_ctx):
        f = SimpleNamespace(status=FILE_STATUS_PENDING, checked_out_by=None)
        assert checkout_error(f) is not None


class TestFolderFileNameTaken:
    def test_taken_in_folder(self, app_ctx, any_folder):
        from app import File

        existing = File.query.filter_by(folder_id=any_folder.id).first()
        if not existing:
            pytest.skip("no files in seed folder")
        assert folder_file_name_taken(any_folder.id, existing.name) is True
        assert folder_file_name_taken(any_folder.id, unique_name("free")) is False
