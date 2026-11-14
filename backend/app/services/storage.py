"""原始文件落地与路径安全。

- 原始文件名只作为元数据保存在数据库，绝不参与路径拼接。
- 磁盘路径由 kb_id(UUID) 和 uuid4 十六进制名组成，用户不可控，
  从根上避免 `../` 与绝对路径穿越。
- 相同内容通过 SHA-256 去重：唯一约束放在数据库层，这里只负责计算。
"""

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# 原始文件后缀 -> 规范文件格式
FORMAT_BY_SUFFIX = {
    ".pdf": "pdf",
    ".md": "markdown",
    ".markdown": "markdown",
}


class UploadValidationError(ValueError):
    """上传文件在进入存储前被拒绝。"""


@dataclass(frozen=True)
class StoredFile:
    original_filename: str
    stored_name: str
    storage_key: str
    file_format: str
    size_bytes: int
    content_hash: str


def resolve_storage_root() -> Path:
    """返回本地文件存储根目录；相对路径固定在 backend/ 下解释。"""
    configured = get_settings().storage_dir
    path = Path(configured)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path


def _sanitize_original_filename(filename: str | None) -> str:
    """从用户输入中提取纯文件名；只做展示，不参与路径拼接。"""
    raw = (filename or "").strip()
    if not raw:
        raise UploadValidationError("文件名为空")
    name = PurePosixPath(raw.replace("\\", "/")).name
    if not name:
        raise UploadValidationError("文件名不合法")
    return name


def canonical_suffix(filename: str | None) -> str:
    """根据后缀返回规范后缀；不支持的类型抛 UploadValidationError。"""
    name = _sanitize_original_filename(filename)
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in FORMAT_BY_SUFFIX:
        raise UploadValidationError("仅支持 PDF 和 Markdown 文件")
    if suffix == ".markdown":
        return ".md"
    return suffix


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_upload(
    *,
    kb_id: uuid.UUID,
    original_filename: str | None,
    data: bytes,
    max_upload_size_bytes: int,
) -> StoredFile:
    """校验并保存上传文件，返回落盘信息。不再接受 UploadFile 对象，便于测试。"""
    original_name = _sanitize_original_filename(original_filename)
    suffix = canonical_suffix(original_name)
    if suffix == ".md":
        file_format = "markdown"
    else:
        file_format = "pdf"

    if len(data) == 0:
        raise UploadValidationError("文件为空，不能上传")
    if len(data) > max_upload_size_bytes:
        raise UploadValidationError(
            f"文件超过大小限制：{len(data)} > {max_upload_size_bytes} 字节"
        )

    stored_name = uuid.uuid4().hex + suffix
    storage_key = PurePosixPath(str(kb_id), stored_name).as_posix()

    root = resolve_storage_root()
    target_dir = root / str(kb_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / stored_name).write_bytes(data)

    return StoredFile(
        original_filename=original_name,
        stored_name=stored_name,
        storage_key=storage_key,
        file_format=file_format,
        size_bytes=len(data),
        content_hash=content_hash(data),
    )


def delete_stored_file(storage_key: str) -> None:
    """数据库写入失败时清理落盘文件；调用方确保 storage_key 来自系统生成。"""
    root = resolve_storage_root()
    safe_path = (root / storage_key).resolve()
    if root.resolve() not in safe_path.parents:
        # 防御性保护：系统生成的 key 不可能越界，但保留最后一道检查
        return
    safe_path.unlink(missing_ok=True)


def read_stored_file(storage_key: str) -> bytes:
    """读取已落盘文件；仅供系统内部在已校验 storage_key 后使用。"""
    root = resolve_storage_root()
    path = (root / storage_key).resolve()
    if root.resolve() not in path.parents:
        raise OSError("非法的存储路径")
    return path.read_bytes()

