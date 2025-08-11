# app/services/yandex_disk.py
import asyncio
import os
import time
import logging
from pathlib import Path
from typing import Optional, BinaryIO, Dict, Any, List, Union
import aiohttp
from urllib.parse import quote_plus

from app.config.yandex_disk import YandexDiskSettings

logger = logging.getLogger(__name__)


class YandexDiskError(Exception):
    """Base exception for Yandex.Disk operations"""
    pass


class YandexDiskClient:
    """Yandex.Disk API client"""

    def __init__(self, settings: YandexDiskSettings):
        self.settings = settings
        self.base_url = settings.base_url
        self.headers = {
            "Authorization": f"OAuth {settings.access_token}",
            "Accept": "application/json"
        }
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.headers)
        return self.session

    async def close(self):
        """Close the client session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _make_request(
            self,
            method: str,
            endpoint: str,
            params: Optional[Dict[str, Any]] = None,
            json_data: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            retry: int = 0
    ) -> Dict[str, Any]:
        """Make an API request with retry logic"""
        url = f"{self.base_url}{endpoint}"
        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)

        session = await self.get_session()

        try:
            async with session.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    data=data,
                    headers=req_headers,
                    timeout=self.settings.upload_timeout
            ) as response:
                if response.status == 200 or response.status == 201:
                    if response.content_type == 'application/json':
                        return await response.json()
                    return {}

                # Handle rate limiting
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', '5'))
                    if retry < self.settings.max_retries:
                        await asyncio.sleep(retry_after)
                        return await self._make_request(
                            method, endpoint, params, json_data, data, headers, retry + 1
                        )

                error_text = await response.text()
                logger.error(f"Yandex.Disk API error: {response.status} - {error_text}")
                raise YandexDiskError(f"Yandex.Disk API error: {response.status} - {error_text}")

        except aiohttp.ClientError as e:
            if retry < self.settings.max_retries:
                await asyncio.sleep(2 ** retry)  # Exponential backoff
                return await self._make_request(
                    method, endpoint, params, json_data, data, headers, retry + 1
                )
            logger.error(f"Yandex.Disk request failed: {str(e)}")
            raise YandexDiskError(f"Request failed: {str(e)}")

    async def create_folder(self, path: str) -> Dict[str, Any]:
        """Create a folder on Yandex.Disk"""
        return await self._make_request(
            "PUT",
            "/resources",
            params={"path": path}
        )

    async def upload_file(
            self,
            local_path: Union[str, Path, BinaryIO],
            remote_path: str,
            overwrite: bool = True
    ) -> Dict[str, Any]:
        """Upload a file to Yandex.Disk"""
        # Get upload URL
        upload_data = await self._make_request(
            "GET",
            "/resources/upload",
            params={
                "path": remote_path,
                "overwrite": str(overwrite).lower()
            }
        )

        if not upload_data.get("href"):
            raise YandexDiskError("Failed to get upload URL")

        # Upload the file
        if isinstance(local_path, (str, Path)):
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local file not found: {local_path}")

            with open(local_path, 'rb') as f:
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                            upload_data["href"],
                            data=f,
                            timeout=self.settings.upload_timeout
                    ) as response:
                        if response.status != 201:
                            error_text = await response.text()
                            raise YandexDiskError(f"Upload failed: {response.status} - {error_text}")
        else:
            # Handle file-like object
            async with aiohttp.ClientSession() as session:
                async with session.put(
                        upload_data["href"],
                        data=local_path,
                        timeout=self.settings.upload_timeout
                ) as response:
                    if response.status != 201:
                        error_text = await response.text()
                        raise YandexDiskError(f"Upload failed: {response.status} - {error_text}")

        # Get file info
        return await self.get_file_info(remote_path)

    async def get_file_info(self, path: str) -> Dict[str, Any]:
        """Get information about a file or folder"""
        return await self._make_request(
            "GET",
            "/resources",
            params={
                "path": path,
                "fields": "name,path,type,size,created,modified,file,preview,public_url"
            }
        )

    async def publish(self, path: str) -> str:
        """Publish a file/folder and return public URL"""
        # First, publish the resource
        await self._make_request(
            "PUT",
            "/resources/publish",
            params={"path": path}
        )

        # Then get public URL
        info = await self.get_file_info(path)
        return info.get("public_url", "")

    async def upload_and_publish(
            self,
            local_path: Union[str, Path, BinaryIO],
            remote_path: str,
            overwrite: bool = True
    ) -> str:
        """Upload a file and make it public, return public URL"""
        # Upload the file
        await self.upload_file(local_path, remote_path, overwrite)

        # Publish and get public URL
        return await self.publish(remote_path)