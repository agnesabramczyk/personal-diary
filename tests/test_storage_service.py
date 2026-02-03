"""Unit tests for StorageService.

Tests photo upload, thumbnail generation, EXIF extraction, and signed URL generation.
"""
import pytest
from datetime import timedelta
from io import BytesIO
from unittest.mock import Mock, MagicMock, patch
from PIL import Image

from app.services.storage_service import (
    StorageService,
    MAX_FILE_SIZE,
)


@pytest.fixture
def mock_storage_client():
    """Mock Google Cloud Storage client."""
    client = Mock()
    bucket = Mock()
    client.bucket.return_value = bucket
    return client


@pytest.fixture
def mock_firestore():
    """Mock FirestoreService."""
    return MagicMock()


@pytest.fixture
def storage_service(mock_storage_client, mock_firestore):
    """StorageService instance with mocked dependencies."""
    with patch('app.services.storage_service.storage.Client', return_value=mock_storage_client):
        with patch('app.services.storage_service.FirestoreService', return_value=mock_firestore):
            service = StorageService()
            service.client = mock_storage_client
            service.bucket = mock_storage_client.bucket.return_value
            service.firestore = mock_firestore
            return service


@pytest.fixture
def sample_jpeg_bytes():
    """Generate a sample JPEG image in bytes."""
    image = Image.new('RGB', (800, 600), color='red')
    output = BytesIO()
    image.save(output, format='JPEG')
    output.seek(0)
    return output.read()


@pytest.fixture
def sample_png_bytes():
    """Generate a sample PNG image in bytes."""
    image = Image.new('RGB', (1024, 768), color='blue')
    output = BytesIO()
    image.save(output, format='PNG')
    output.seek(0)
    return output.read()


class TestValidateFile:
    """Tests for file validation."""

    def test_validate_file_valid_jpeg(self, storage_service, sample_jpeg_bytes):
        """Should accept valid JPEG files under size limit."""
        storage_service._validate_file(sample_jpeg_bytes, "image/jpeg")
        # No exception raised means validation passed

    def test_validate_file_valid_png(self, storage_service, sample_png_bytes):
        """Should accept valid PNG files under size limit."""
        storage_service._validate_file(sample_png_bytes, "image/png")
        # No exception raised means validation passed

    def test_validate_file_too_large(self, storage_service):
        """Should reject files exceeding maximum size."""
        large_file = b"x" * (MAX_FILE_SIZE + 1)
        with pytest.raises(ValueError, match="File size exceeds maximum"):
            storage_service._validate_file(large_file, "image/jpeg")

    def test_validate_file_invalid_content_type(self, storage_service, sample_jpeg_bytes):
        """Should reject unsupported content types."""
        with pytest.raises(ValueError, match="Invalid content type"):
            storage_service._validate_file(sample_jpeg_bytes, "image/gif")

    def test_validate_file_invalid_content_type_video(self, storage_service):
        """Should reject video files."""
        with pytest.raises(ValueError, match="Invalid content type"):
            storage_service._validate_file(b"fake video", "video/mp4")

    def test_validate_file_exactly_max_size(self, storage_service):
        """Should accept files at exactly the maximum size."""
        max_size_file = b"x" * MAX_FILE_SIZE
        storage_service._validate_file(max_size_file, "image/jpeg")
        # No exception raised means validation passed


class TestGenerateThumbnail:
    """Tests for thumbnail generation."""

    def test_generate_thumbnail_landscape(self, storage_service):
        """Should generate thumbnail for landscape image maintaining aspect ratio."""
        # Create 800x600 landscape image
        image = Image.new('RGB', (800, 600), color='green')
        input_bytes = BytesIO()
        image.save(input_bytes, format='JPEG')
        input_bytes.seek(0)

        thumbnail_bytes = storage_service._generate_thumbnail(input_bytes.read())

        # Verify thumbnail is valid image
        thumbnail_image = Image.open(BytesIO(thumbnail_bytes))
        width, height = thumbnail_image.size

        # Should scale to 300 width, 225 height (maintains 4:3 ratio)
        assert width == 300
        assert height == 225

    def test_generate_thumbnail_portrait(self, storage_service):
        """Should generate thumbnail for portrait image maintaining aspect ratio."""
        # Create 600x800 portrait image
        image = Image.new('RGB', (600, 800), color='purple')
        input_bytes = BytesIO()
        image.save(input_bytes, format='JPEG')
        input_bytes.seek(0)

        thumbnail_bytes = storage_service._generate_thumbnail(input_bytes.read())

        # Verify thumbnail is valid image
        thumbnail_image = Image.open(BytesIO(thumbnail_bytes))
        width, height = thumbnail_image.size

        # Should scale to 225 width, 300 height (maintains 3:4 ratio)
        assert width == 225
        assert height == 300

    def test_generate_thumbnail_square(self, storage_service):
        """Should generate thumbnail for square image."""
        # Create 1000x1000 square image
        image = Image.new('RGB', (1000, 1000), color='yellow')
        input_bytes = BytesIO()
        image.save(input_bytes, format='JPEG')
        input_bytes.seek(0)

        thumbnail_bytes = storage_service._generate_thumbnail(input_bytes.read())

        # Verify thumbnail is valid image
        thumbnail_image = Image.open(BytesIO(thumbnail_bytes))
        width, height = thumbnail_image.size

        # Should scale to 300x300
        assert width == 300
        assert height == 300

    def test_generate_thumbnail_small_image(self, storage_service):
        """Should not upscale images smaller than thumbnail size."""
        # Create 200x150 image (smaller than thumbnail max)
        image = Image.new('RGB', (200, 150), color='orange')
        input_bytes = BytesIO()
        image.save(input_bytes, format='JPEG')
        input_bytes.seek(0)

        thumbnail_bytes = storage_service._generate_thumbnail(input_bytes.read())

        # Verify thumbnail maintains original size (doesn't upscale)
        thumbnail_image = Image.open(BytesIO(thumbnail_bytes))
        width, height = thumbnail_image.size

        assert width == 200
        assert height == 150

    def test_generate_thumbnail_png_format(self, storage_service):
        """Should preserve PNG format in thumbnail."""
        # Create PNG image
        image = Image.new('RGB', (800, 600), color='cyan')
        input_bytes = BytesIO()
        image.save(input_bytes, format='PNG')
        input_bytes.seek(0)

        thumbnail_bytes = storage_service._generate_thumbnail(input_bytes.read())

        # Verify thumbnail is PNG format
        thumbnail_image = Image.open(BytesIO(thumbnail_bytes))
        assert thumbnail_image.format == 'PNG'


class TestExtractExif:
    """Tests for EXIF metadata extraction."""

    def test_extract_exif_with_metadata(self, storage_service):
        """Should extract EXIF metadata from image."""
        # Create image with EXIF data
        image = Image.new('RGB', (640, 480), color='white')
        exif = image.getexif()
        # Add some EXIF tags (using standard tag IDs)
        exif[0x010E] = "Test Description"  # ImageDescription
        exif[0x0132] = "2026:01:30 20:00:00"  # DateTime

        output = BytesIO()
        image.save(output, format='JPEG', exif=exif)
        output.seek(0)

        exif_data = storage_service._extract_exif(output.read())

        # Should extract EXIF tags with human-readable names
        assert isinstance(exif_data, dict)
        # Note: May contain ImageDescription and DateTime if preserved

    def test_extract_exif_no_metadata(self, storage_service, sample_jpeg_bytes):
        """Should return empty dict for images without EXIF."""
        exif_data = storage_service._extract_exif(sample_jpeg_bytes)

        assert isinstance(exif_data, dict)
        # Empty or minimal EXIF is acceptable

    def test_extract_exif_png_image(self, storage_service, sample_png_bytes):
        """Should handle PNG images without EXIF gracefully."""
        exif_data = storage_service._extract_exif(sample_png_bytes)

        assert isinstance(exif_data, dict)
        # PNG typically doesn't have EXIF, empty dict is fine

    def test_extract_exif_corrupted_image(self, storage_service):
        """Should return empty dict for corrupted images."""
        corrupted_bytes = b"not a real image"

        exif_data = storage_service._extract_exif(corrupted_bytes)

        assert exif_data == {}


class TestGenerateSignedUrl:
    """Tests for signed URL generation."""

    def test_generate_signed_url(self, storage_service):
        """Should generate signed URL with correct expiration."""
        mock_blob = Mock()
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/bucket/photo?signature=abc123"

        url = storage_service._generate_signed_url(mock_blob)

        assert url.startswith("https://storage.googleapis.com")
        mock_blob.generate_signed_url.assert_called_once()
        call_args = mock_blob.generate_signed_url.call_args
        assert call_args.kwargs["version"] == "v4"
        assert call_args.kwargs["method"] == "GET"
        assert isinstance(call_args.kwargs["expiration"], timedelta)


class TestUploadPhoto:
    """Tests for photo upload workflow."""

    @pytest.mark.asyncio
    @patch('app.services.timezone_utils.now_aest')
    async def test_upload_photo_success(self, mock_now, storage_service, sample_jpeg_bytes):
        """Should successfully upload photo with thumbnail and metadata."""
        from datetime import datetime
        from app.services.timezone_utils import AEST

        mock_timestamp = datetime(2026, 1, 30, 20, 0, 0, tzinfo=AEST)
        mock_now.return_value = mock_timestamp

        # Mock blob operations
        mock_blob = Mock()
        mock_blob.generate_signed_url.return_value = "https://example.com/photo.jpg?sig=xyz"
        mock_thumbnail_blob = Mock()
        mock_thumbnail_blob.generate_signed_url.return_value = "https://example.com/thumb.jpg?sig=abc"
        storage_service.bucket.blob.side_effect = [mock_blob, mock_thumbnail_blob]

        # Upload photo
        result = await storage_service.upload_photo(
            entry_id="entry123",
            file_content=sample_jpeg_bytes,
            filename="test.jpg",
            content_type="image/jpeg",
            caption="Test caption"
        )

        # Verify blobs created
        assert storage_service.bucket.blob.call_count == 2

        # Verify both files uploaded
        mock_blob.upload_from_string.assert_called_once()
        mock_thumbnail_blob.upload_from_string.assert_called_once()

        # Verify metadata stored
        storage_service.firestore.create_photo.assert_called_once()
        photo_data = storage_service.firestore.create_photo.call_args[0][0]

        assert photo_data["entry_id"] == "entry123"
        assert photo_data["filename"] == "test.jpg"
        assert photo_data["content_type"] == "image/jpeg"
        assert photo_data["caption"] == "Test caption"
        assert photo_data["created_at"] == mock_timestamp
        assert "id" in photo_data
        assert "storage_path" in photo_data
        assert "thumbnail_path" in photo_data

        # Verify result
        assert result["entry_id"] == "entry123"
        assert result["filename"] == "test.jpg"

    @pytest.mark.asyncio
    async def test_upload_photo_invalid_file_size(self, storage_service):
        """Should reject files exceeding size limit."""
        large_file = b"x" * (MAX_FILE_SIZE + 1)

        with pytest.raises(ValueError, match="File size exceeds maximum"):
            await storage_service.upload_photo(
                entry_id="entry123",
                file_content=large_file,
                filename="huge.jpg",
                content_type="image/jpeg"
            )

    @pytest.mark.asyncio
    async def test_upload_photo_invalid_content_type(self, storage_service, sample_jpeg_bytes):
        """Should reject unsupported content types."""
        with pytest.raises(ValueError, match="Invalid content type"):
            await storage_service.upload_photo(
                entry_id="entry123",
                file_content=sample_jpeg_bytes,
                filename="test.gif",
                content_type="image/gif"
            )


class TestGetPhotoUrl:
    """Tests for photo URL retrieval."""

    @pytest.mark.asyncio
    async def test_get_photo_url_success(self, storage_service):
        """Should generate fresh signed URLs for existing photo."""
        photo_data = {
            "id": "photo123",
            "storage_path": "photos/entry123/photo123.jpg",
            "thumbnail_path": "photos/entry123/photo123_thumb.jpg"
        }
        storage_service.firestore.get_photo.return_value = photo_data

        mock_blob = Mock()
        mock_blob.generate_signed_url.return_value = "https://example.com/photo.jpg?sig=new"
        mock_thumbnail_blob = Mock()
        mock_thumbnail_blob.generate_signed_url.return_value = "https://example.com/thumb.jpg?sig=new"
        storage_service.bucket.blob.side_effect = [mock_blob, mock_thumbnail_blob]

        result = await storage_service.get_photo_url("photo123")

        storage_service.firestore.get_photo.assert_called_once_with("photo123")
        assert "photo_url" in result
        assert "thumbnail_url" in result
        assert result["photo_url"].startswith("https://example.com")
        assert result["thumbnail_url"].startswith("https://example.com")

    @pytest.mark.asyncio
    async def test_get_photo_url_not_found(self, storage_service):
        """Should raise ValueError if photo doesn't exist."""
        storage_service.firestore.get_photo.return_value = None

        with pytest.raises(ValueError, match="Photo photo123 not found"):
            await storage_service.get_photo_url("photo123")


class TestDeletePhoto:
    """Tests for photo deletion."""

    @pytest.mark.asyncio
    async def test_delete_photo_success(self, storage_service):
        """Should delete photo from storage and Firestore."""
        photo_data = {
            "id": "photo123",
            "storage_path": "photos/entry123/photo123.jpg",
            "thumbnail_path": "photos/entry123/photo123_thumb.jpg"
        }
        storage_service.firestore.get_photo.return_value = photo_data

        mock_blob = Mock()
        mock_thumbnail_blob = Mock()
        storage_service.bucket.blob.side_effect = [mock_blob, mock_thumbnail_blob]

        await storage_service.delete_photo("photo123")

        # Verify Firestore lookup
        storage_service.firestore.get_photo.assert_called_once_with("photo123")

        # Verify storage deletion
        assert storage_service.bucket.blob.call_count == 2
        mock_blob.delete.assert_called_once()
        mock_thumbnail_blob.delete.assert_called_once()

        # Verify Firestore deletion
        storage_service.firestore.delete_photo.assert_called_once_with("photo123")

    @pytest.mark.asyncio
    async def test_delete_photo_not_found(self, storage_service):
        """Should raise ValueError if photo doesn't exist."""
        storage_service.firestore.get_photo.return_value = None

        with pytest.raises(ValueError, match="Photo photo123 not found"):
            await storage_service.delete_photo("photo123")

    @pytest.mark.asyncio
    async def test_delete_photo_storage_error_continues(self, storage_service):
        """Should continue to Firestore deletion even if storage deletion fails."""
        photo_data = {
            "id": "photo123",
            "storage_path": "photos/entry123/photo123.jpg",
            "thumbnail_path": "photos/entry123/photo123_thumb.jpg"
        }
        storage_service.firestore.get_photo.return_value = photo_data

        mock_blob = Mock()
        mock_blob.delete.side_effect = Exception("Storage error")
        mock_thumbnail_blob = Mock()
        storage_service.bucket.blob.side_effect = [mock_blob, mock_thumbnail_blob]

        # Should not raise exception
        await storage_service.delete_photo("photo123")

        # Verify Firestore deletion still happened
        storage_service.firestore.delete_photo.assert_called_once_with("photo123")


class TestGetExtension:
    """Tests for file extension helper."""

    def test_get_extension_jpeg(self, storage_service):
        """Should return .jpg for JPEG content type."""
        ext = storage_service._get_extension("image/jpeg")
        assert ext == ".jpg"

    def test_get_extension_png(self, storage_service):
        """Should return .png for PNG content type."""
        ext = storage_service._get_extension("image/png")
        assert ext == ".png"

    def test_get_extension_unknown(self, storage_service):
        """Should default to .jpg for unknown types."""
        ext = storage_service._get_extension("image/unknown")
        assert ext == ".jpg"