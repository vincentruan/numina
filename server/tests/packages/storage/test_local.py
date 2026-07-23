"""Tests for packages.storage.local.LocalStorageBackend.

覆盖：
- save 的两种路径布局（带 family_id/user_id 与 legacy 无 id）
- _validate_id 对非法 id 的拒绝
- 路径越界（path traversal）防护
- delete 的正常删除 / 缺失文件告警不抛错 / 越界拒绝
- get_url 的根相对 URL
"""

from __future__ import annotations

import pytest

from packages.storage.local import LocalStorageBackend, _validate_id


@pytest.fixture()
def backend(tmp_path):
    """以 tmp_path 作为 upload_dir 的 backend 实例。"""
    return LocalStorageBackend(str(tmp_path))


class TestSavePathLayout:
    """save 的目录布局与返回值。"""

    async def test_save_with_family_and_user_id(self, backend, tmp_path):
        remote = await backend.save(
            b"hello", "a.png", "2026-07-22", family_id="fam1", user_id="u2"
        )
        # remote_path 不含 uploads/ 前缀（get_url 时再拼）
        assert remote == "fam1/u2/2026-07-22/a.png"
        # 实际落盘位置：{upload_dir}/uploads/{family_id}/{user_id}/{date}/{filename}
        expected = tmp_path / "uploads" / "fam1" / "u2" / "2026-07-22" / "a.png"
        assert expected.read_bytes() == b"hello"

    async def test_save_legacy_path_without_ids(self, backend, tmp_path):
        remote = await backend.save(b"data", "b.jpg", "2026-01-01")
        assert remote == "images/2026-01-01/b.jpg"
        expected = tmp_path / "uploads" / "images" / "2026-01-01" / "b.jpg"
        assert expected.read_bytes() == b"data"

    async def test_save_only_family_id_falls_back_to_legacy(self, backend, tmp_path):
        """只有 family_id 没有 user_id 时走 legacy 路径（需两者同时存在）。"""
        remote = await backend.save(b"x", "c.png", "2026-02-02", family_id="fam1")
        assert remote == "images/2026-02-02/c.png"
        assert (tmp_path / "uploads" / "images" / "2026-02-02" / "c.png").exists()

    async def test_save_creates_nested_dirs(self, backend, tmp_path):
        """parents=True 应自动创建多级目录。"""
        await backend.save(b"x", "d.png", "2026-03-03", family_id="f", user_id="u")
        assert (tmp_path / "uploads" / "f" / "u" / "2026-03-03").is_dir()

    async def test_save_overwrites_existing_file(self, backend, tmp_path):
        await backend.save(b"old", "e.png", "2026-04-04", family_id="f", user_id="u")
        await backend.save(b"new", "e.png", "2026-04-04", family_id="f", user_id="u")
        expected = tmp_path / "uploads" / "f" / "u" / "2026-04-04" / "e.png"
        assert expected.read_bytes() == b"new"


class TestValidateId:
    """_validate_id 的合法/非法输入。"""

    @pytest.mark.parametrize("value", ["abc", "A1_-", "fam-123_XYZ", "0"])
    def test_valid_ids_accepted(self, value):
        _validate_id(value, "family_id")  # 不抛错

    @pytest.mark.parametrize(
        "value",
        ["", "..", "a/b", "a\\b", "a b", "a.b", "../etc", "a;b", "中文"],
    )
    def test_invalid_ids_rejected(self, value):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id(value, "family_id")

    async def test_save_rejects_bad_family_id(self, backend):
        with pytest.raises(ValueError, match="Invalid family_id"):
            await backend.save(b"x", "f.png", "d", family_id="../evil", user_id="u")

    async def test_save_rejects_bad_user_id(self, backend):
        with pytest.raises(ValueError, match="Invalid user_id"):
            await backend.save(b"x", "f.png", "d", family_id="f", user_id="a/b")


class TestSavePathTraversal:
    """save 的路径越界防护。

    由于 family_id/user_id 已被 _validate_id 限制为安全字符，能触发越界检查的
    现实途径是 filename/date_dir 含 `..`。resolved 路径越界时应删除已写文件并抛错。
    """

    async def test_filename_traversal_raises_and_removes(self, backend, tmp_path):
        # legacy 路径 target_dir={upload_dir}/uploads/images/{date}；
        # 需足够多的 .. 才能真正越过 upload_dir 根（4 级）。
        with pytest.raises(ValueError, match="路径越界"):
            await backend.save(b"x", "../../../../evil.png", "2026-01-01")
        # 越界文件不应残留（save 在抛错前 os.remove）
        assert not (tmp_path / "evil.png").exists()
        assert not (tmp_path.parent / "evil.png").exists()

    async def test_filename_traversal_within_upload_dir_allowed(self, backend, tmp_path):
        # ../../evil.png 只上溯到 uploads/ 内，仍在 upload_dir 下 → 不视为越界。
        # 这记录了防护的边界：guard 只拦截逃出 upload_dir 的写入。
        remote = await backend.save(b"x", "../../ok.png", "2026-01-01")
        assert (tmp_path / "uploads" / "ok.png").exists()
        assert remote == "images/2026-01-01/../../ok.png"

    async def test_date_dir_traversal_raises(self, backend, tmp_path):
        # date_dir 越出 upload_dir 根：uploads/f/u/{date} 上溯 5 级
        with pytest.raises(ValueError, match="路径越界"):
            await backend.save(b"x", "f.png", "../../../../../..", family_id="f", user_id="u")


class TestDelete:
    """delete 的正常/缺失/越界行为。"""

    async def test_delete_existing_file(self, backend, tmp_path):
        remote = await backend.save(b"x", "f.png", "2026-01-01", family_id="f", user_id="u")
        file_path = tmp_path / "uploads" / "f" / "u" / "2026-01-01" / "f.png"
        assert file_path.exists()
        await backend.delete(remote)
        assert not file_path.exists()

    async def test_delete_missing_file_logs_warning_no_raise(self, backend, caplog):
        # 文件不存在：记录 warning，不抛异常
        await backend.delete("f/u/2026-01-01/nonexistent.png")

    async def test_delete_path_traversal_raises(self, backend):
        with pytest.raises(ValueError, match="路径越界"):
            await backend.delete("../../outside.png")

    async def test_delete_absolute_path_traversal_raises(self, backend):
        # 以绝对路径形式越界（resolve 后不在 upload_dir 内）
        with pytest.raises(ValueError, match="路径越界"):
            await backend.delete("/etc/passwd")


class TestGetUrl:
    """get_url 返回 StaticFiles 挂载的根相对 URL。"""

    def test_get_url(self, backend):
        assert backend.get_url("fam1/u2/2026-01-01/a.png") == "/uploads/fam1/u2/2026-01-01/a.png"

    def test_get_url_legacy(self, backend):
        assert backend.get_url("images/2026-01-01/a.png") == "/uploads/images/2026-01-01/a.png"
