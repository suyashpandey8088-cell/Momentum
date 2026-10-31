import hashlib
import hmac
import time
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from core.config import get_settings

EXTENSIONS = {'.mp3', '.wav', '.m4a', '.mp4', '.webm'}

def validate_magic(header: bytes, extension: str) -> bool:
    if extension == '.wav': return header[:4] == b'RIFF' and header[8:12] == b'WAVE'
    if extension in {'.m4a', '.mp4'}: return header[4:8] == b'ftyp'
    if extension == '.mp3': return header[:3] == b'ID3' or (len(header) > 1 and header[0] == 255 and header[1] & 224 == 224)
    if extension == '.webm': return header[:4] == b'\x1a\x45\xdf\xa3'
    return False

def store_upload(file: UploadFile, org_id: str) -> tuple[str, str, int]:
    settings = get_settings()
    filename = Path(file.filename or 'recording').name[:200]
    extension = Path(filename).suffix.lower()
    if extension not in EXTENSIONS: raise HTTPException(422, 'Supported recording formats: MP3, WAV, M4A, MP4, and WebM.')
    key = f'{org_id}/{uuid4().hex}{extension}'
    path = settings.storage_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with path.open('wb') as output:
            header = file.file.read(64)
            if not validate_magic(header, extension): raise HTTPException(422, 'The file content does not match its recording format.')
            output.write(header); size += len(header)
            while chunk := file.file.read(1024*1024):
                size += len(chunk)
                if size > settings.max_upload_mb*1024*1024: raise HTTPException(413, f'Recordings must be smaller than {settings.max_upload_mb} MB.')
                output.write(chunk)
        if size < 16: raise HTTPException(422, 'This recording is empty.')
        from services.object_storage import upload, configured
        upload(key, str(path), file.content_type or 'application/octet-stream')
        if configured(): path.unlink(missing_ok=True)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return key, filename, size

def recording_path(key: str) -> Path:
    root = get_settings().storage_dir.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root) or not path.is_file(): raise HTTPException(404, 'Recording not found.')
    return path

def delete_recording(key: str):
    if not key: return
    root = get_settings().storage_dir.resolve()
    path = (root / key).resolve()
    if path.is_relative_to(root): path.unlink(missing_ok=True)
    from services.object_storage import remove
    remove(key)

def signature(meeting_id: str, expires: int) -> str:
    return hmac.new(get_settings().token_encryption_key.encode() or b'momentum-local-signing', f'{meeting_id}:{expires}'.encode(), hashlib.sha256).hexdigest()

def signed_recording_url(meeting_id: str) -> str:
    expires = int(time.time()) + 900
    return f'/api/meetings/{meeting_id}/recording?expires={expires}&signature={signature(meeting_id, expires)}'

def verify_signature(meeting_id: str, expires: int, provided: str):
    if expires < time.time() or expires > time.time()+901 or not hmac.compare_digest(signature(meeting_id, expires), provided): raise HTTPException(403, 'This recording link has expired. Request a new one.')
