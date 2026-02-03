"""Cloud Storage service for photo management.

Handles photo uploads, thumbnail generation, EXIF extraction, and signed URL generation.
"""
import asyncio
from datetime import timedelta
from io import BytesIO
from typing import Dict, Any, Optional
import uuid

from google.cloud import storage
from google.cloud.storage import Blob
from google.oauth2 import service_account
from PIL import Image
from PIL.ExifTags import TAGS

from app.config import settings
from app.services.firestore_service import FirestoreService


# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
THUMBNAIL_MAX_SIZE = 300  # pixels for both width and height


class StorageService:
    """Service for managing photo storage in Google Cloud Storage."""

    def __init__(self) -> None:
        """Initialise the storage service with GCP client."""
        # Load service account credentials for signed URL generation
        # If credentials path is None, use default credentials (Cloud Run Workload Identity)
        if settings.google_application_credentials:
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials
            )
            self.client = storage.Client(
                project=settings.gcp_project_id,
                credentials=credentials
            )
        else:
            # Use default credentials (Application Default Credentials)
            self.client = storage.Client(project=settings.gcp_project_id)

        self.bucket = self.client.bucket(settings.storage_bucket)
        self.firestore = FirestoreService(
            project_id=settings.gcp_project_id,
            database=settings.firestore_database,
            credentials_path=settings.google_application_credentials,
        )

    async def upload_photo(
        self,
        entry_id: str,
        file_content: bytes,
        filename: str,
        content_type: str,
        caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a photo with thumbnail generation and EXIF extraction.

        Args:
            entry_id: Entry identifier this photo belongs to
            file_content: Raw file bytes
            filename: Original filename
            content_type: MIME type (must be image/jpeg or image/png)
            caption: Optional caption for the photo

        Returns:
            Photo metadata dictionary including URLs and EXIF data

        Raises:
            ValueError: If file validation fails
            Exception: If upload or processing fails
        """
        loop = asyncio.get_event_loop()
        
        # Validate file (synchronous, fast operation)
        self._validate_file(file_content, content_type)

        # Generate unique photo ID and storage paths
        photo_id = str(uuid.uuid4())
        extension = self._get_extension(content_type)
        storage_path = f"photos/{entry_id}/{photo_id}{extension}"
        thumbnail_path = f"photos/{entry_id}/{photo_id}_thumb{extension}"

        # Run blocking operations in executor
        exif_data, thumbnail_bytes = await loop.run_in_executor(
            None,
            self._upload_photo_sync,
            file_content,
            content_type,
            storage_path,
            thumbnail_path,
        )

        # Store photo metadata in Firestore
        from app.services.timezone_utils import now_aest

        photo_data = {
            "id": photo_id,
            "entry_id": entry_id,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(file_content),
            "storage_path": storage_path,
            "thumbnail_path": thumbnail_path,
            "photo_url": exif_data["photo_url"],
            "thumbnail_url": exif_data["thumbnail_url"],
            "exif_data": exif_data["exif_metadata"],
            "caption": caption,
            "created_at": now_aest(),
        }

        self.firestore.create_photo(photo_data)

        return photo_data

    def _upload_photo_sync(
        self,
        file_content: bytes,
        content_type: str,
        storage_path: str,
        thumbnail_path: str,
    ) -> tuple[Dict[str, Any], bytes]:
        """Synchronous helper for photo upload blocking operations.

        Args:
            file_content: Raw file bytes
            content_type: MIME type
            storage_path: Cloud Storage path for original photo
            thumbnail_path: Cloud Storage path for thumbnail

        Returns:
            Tuple of (result dict with URLs and EXIF, thumbnail bytes)
        """
        # Extract EXIF metadata before processing
        exif_metadata = self._extract_exif(file_content)

        # Upload original photo
        blob = self.bucket.blob(storage_path)
        blob.upload_from_string(file_content, content_type=content_type)

        # Generate and upload thumbnail
        thumbnail_bytes = self._generate_thumbnail(file_content)
        thumbnail_blob = self.bucket.blob(thumbnail_path)
        thumbnail_blob.upload_from_string(thumbnail_bytes, content_type=content_type)

        # Generate signed URLs
        photo_url = self._generate_signed_url(blob)
        thumbnail_url = self._generate_signed_url(thumbnail_blob)

        return {
            "photo_url": photo_url,
            "thumbnail_url": thumbnail_url,
            "exif_metadata": exif_metadata,
        }, thumbnail_bytes

    async def get_photo_url(self, photo_id: str) -> Dict[str, str]:
        """Get signed URLs for a photo.

        Args:
            photo_id: Photo identifier

        Returns:
            Dictionary with photo_url and thumbnail_url

        Raises:
            ValueError: If photo not found
        """
        photo = self.firestore.get_photo(photo_id)
        if not photo:
            raise ValueError(f"Photo {photo_id} not found")

        # Generate fresh signed URLs in executor (blocking operation)
        loop = asyncio.get_event_loop()
        urls = await loop.run_in_executor(
            None,
            self._get_photo_url_sync,
            photo["storage_path"],
            photo["thumbnail_path"],
        )

        return urls

    def _get_photo_url_sync(self, storage_path: str, thumbnail_path: str) -> Dict[str, str]:
        """Synchronous helper for generating signed URLs.

        Args:
            storage_path: Cloud Storage path for original photo
            thumbnail_path: Cloud Storage path for thumbnail

        Returns:
            Dictionary with photo_url and thumbnail_url
        """
        blob = self.bucket.blob(storage_path)
        thumbnail_blob = self.bucket.blob(thumbnail_path)

        return {
            "photo_url": self._generate_signed_url(blob),
            "thumbnail_url": self._generate_signed_url(thumbnail_blob),
        }

    async def delete_photo(self, photo_id: str) -> None:
        """Delete a photo from storage and Firestore.

        Args:
            photo_id: Photo identifier

        Raises:
            ValueError: If photo not found
        """
        photo = self.firestore.get_photo(photo_id)
        if not photo:
            raise ValueError(f"Photo {photo_id} not found")

        # Delete from Cloud Storage in executor (blocking I/O)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._delete_photo_sync,
            photo["storage_path"],
            photo["thumbnail_path"],
        )

        # Delete from Firestore
        self.firestore.delete_photo(photo_id)

    def _delete_photo_sync(self, storage_path: str, thumbnail_path: str) -> None:
        """Synchronous helper for deleting photos from Cloud Storage.

        Args:
            storage_path: Cloud Storage path for original photo
            thumbnail_path: Cloud Storage path for thumbnail
        """
        # Delete from Cloud Storage
        try:
            blob = self.bucket.blob(storage_path)
            blob.delete()
        except Exception:
            # Continue even if blob doesn't exist
            pass

        try:
            thumbnail_blob = self.bucket.blob(thumbnail_path)
            thumbnail_blob.delete()
        except Exception:
            # Continue even if thumbnail doesn't exist
            pass

    def _validate_file(self, file_content: bytes, content_type: str) -> None:
        """Validate file size and content type.

        Args:
            file_content: Raw file bytes
            content_type: MIME type

        Raises:
            ValueError: If validation fails
        """
        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(
                f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / 1024 / 1024}MB"
            )

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"Invalid content type. Must be one of: {', '.join(ALLOWED_CONTENT_TYPES)}"
            )

    def _get_extension(self, content_type: str) -> str:
        """Get file extension from content type.

        Args:
            content_type: MIME type

        Returns:
            File extension including dot
        """
        extensions = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
        }
        return extensions.get(content_type, ".jpg")

    def _generate_thumbnail(self, file_content: bytes) -> bytes:
        """Generate a thumbnail from image bytes.

        Creates a thumbnail with maximum dimension of 300px while maintaining aspect ratio.

        Args:
            file_content: Raw image bytes

        Returns:
            Thumbnail image bytes
        """
        image = Image.open(BytesIO(file_content))

        # Maintain aspect ratio while ensuring max dimension is THUMBNAIL_MAX_SIZE
        image.thumbnail((THUMBNAIL_MAX_SIZE, THUMBNAIL_MAX_SIZE), Image.Resampling.LANCZOS)

        # Save thumbnail to bytes
        output = BytesIO()
        # Preserve original format
        image_format = image.format or "JPEG"
        image.save(output, format=image_format, quality=85, optimize=True)
        output.seek(0)

        return output.read()

    def _extract_exif(self, file_content: bytes) -> Dict[str, Any]:
        """Extract EXIF metadata from image bytes.

        Args:
            file_content: Raw image bytes

        Returns:
            Dictionary of EXIF metadata with human-readable tag names
        """
        exif_data = {}

        try:
            image = Image.open(BytesIO(file_content))
            exif = image.getexif()

            if exif:
                for tag_id, value in exif.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    # Convert bytes to string for JSON serialisation
                    if isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8")
                        except UnicodeDecodeError:
                            value = str(value)
                    exif_data[str(tag_name)] = value
        except Exception:
            # If EXIF extraction fails, return empty dict
            pass

        return exif_data

    def _generate_signed_url(self, blob: Blob) -> str:
        """Generate a signed URL for a Cloud Storage blob.

        Args:
            blob: Cloud Storage blob

        Returns:
            Signed URL with expiration
        """
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=settings.signed_url_expiration),
            method="GET",
        )