import logging
from datetime import time
from pathlib import Path
from typing import Optional, Dict, Any, BinaryIO
import hashlib
import os

from app.services.yandex_disk import YandexDiskClient, YandexDiskError
from app.db.models import Document
from app.db.repository import session_scope

logger = logging.getLogger(__name__)


class DocumentStorage:
    """Service for handling document storage operations"""

    def __init__(self, yadisk: YandexDiskClient, base_path: str = "doc-flow-bot"):
        self.yadisk = yadisk
        self.base_path = base_path

    async def _get_remote_path(self, app_id: int, filename: str) -> str:
        """Generate remote path for a file"""
        return f"{self.base_path}/app_{app_id}/{filename}"

    async def upload_document(
            self,
            app_id: int,
            file_obj: BinaryIO,
            filename: str,
            doc_type: str,
            user_id: int
    ) -> Dict[str, Any]:
        """Upload a document to Yandex.Disk and save metadata to DB"""
        # Generate a unique filename
        file_ext = Path(filename).suffix
        file_hash = hashlib.sha256(filename.encode() + str(time.time()).encode()).hexdigest()[:16]
        safe_filename = f"{file_hash}{file_ext}"

        # Upload to Yandex.Disk
        remote_path = await self._get_remote_path(app_id, safe_filename)
        file_info = await self.yadisk.upload_file(file_obj, remote_path)

        # Publish the file to get public URL
        public_url = await self.yadisk.publish(remote_path)

        # Save to database
        with session_scope() as s:
            doc = Document(
                application_id=app_id,
                doc_type=doc_type,
                file_name=filename,
                remote_path=remote_path,
                public_url=public_url,
                uploaded_by=user_id,
                file_size=file_info.get("size", 0)
            )
            s.add(doc)
            s.flush()

            return {
                "id": doc.id,
                "filename": filename,
                "public_url": public_url,
                "size": file_info.get("size", 0),
                "created_at": doc.created_at.isoformat()
            }


    async def get_document_url(self, doc_id: int) -> Optional[str]:
        """Get public URL for a document"""
        with session_scope() as s:
            doc = s.query(Document).get(doc_id)
            if not doc:
                return None
            return doc.public_url

    async def delete_document(self, doc_id: int) -> bool:
        """Delete a document from Yandex.Disk and DB"""
        with session_scope() as s:
            doc = s.query(Document).get(doc_id)
            if not doc:
                return False

            try:
                # Delete from Yandex.Disk
                await self.yadisk._make_request(
                    "DELETE",
                    "/resources",
                    params={"path": doc.remote_path, "permanently": "true"}
                )

                # Delete from DB
                s.delete(doc)
                return True

            except YandexDiskError as e:
                logger.error(f"Failed to delete document {doc_id}: {str(e)}")
                return False


    async def get_application_documents(self, app_id: int) -> Dict[str, Any]:
        """Get all documents for an application"""
        with session_scope() as s:
            docs = s.query(Document).filter(Document.application_id == app_id).all()
            return {
                "application_id": app_id,
                "documents": [
                    {
                        "id": doc.id,
                        "type": doc.doc_type,
                        "filename": doc.file_name,
                        "size": doc.file_size,
                        "public_url": doc.public_url,
                        "uploaded_at": doc.created_at.isoformat()
                    }
                    for doc in docs
                ]
            }