from supabase import Client
from app.db.supabase import get_supabase_client
import os
from typing import Optional


class StorageService:
    """Service for Supabase Storage operations"""

    BUCKET_CVS = "cvs"
    BUCKET_VIDEOS = "intro-videos"
    BUCKET_PHOTOS = "headshot-photos"

    @staticmethod
    def upload_file(
        bucket_name: str,
        file_path: str,
        file_data: bytes,
        content_type: str
    ) -> dict:
        """
        Upload file to Supabase Storage
        Returns upload response with path
        """
        supabase = get_supabase_client()

        response = supabase.storage.from_(bucket_name).upload(
            file_path,
            file_data,
            file_options={"content-type": content_type}
        )

        return response

    @staticmethod
    def get_public_url(bucket_name: str, file_path: str) -> str:
        """
        Get public URL for a file
        Note: For private buckets, use get_signed_url instead
        """
        supabase = get_supabase_client()
        response = supabase.storage.from_(bucket_name).get_public_url(file_path)
        return response

    @staticmethod
    def get_signed_url(bucket_name: str, file_path: str, expires_in: int = 3600) -> str:
        """
        Get signed URL for private file access
        expires_in: seconds until URL expires (default 1 hour)
        """
        supabase = get_supabase_client()
        response = supabase.storage.from_(bucket_name).create_signed_url(
            file_path,
            expires_in
        )
        return response.get("signedURL", "")

    @staticmethod
    def delete_file(bucket_name: str, file_path: str) -> dict:
        """Delete file from storage"""
        supabase = get_supabase_client()
        response = supabase.storage.from_(bucket_name).remove([file_path])
        return response

    @staticmethod
    def upload_teacher_cv(teacher_id: int, file_data: bytes, filename: str) -> str:
        """
        Upload teacher CV and return storage path
        """
        # Determine content type from filename
        extension = filename.split('.')[-1].lower()
        content_type_map = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        content_type = content_type_map.get(extension, 'application/octet-stream')

        # Path format: {teacher_id}/cv.{extension}
        file_path = f"{teacher_id}/cv.{extension}"

        # Delete old file if exists
        try:
            StorageService.delete_file(StorageService.BUCKET_CVS, file_path)
        except:
            pass  # File doesn't exist, that's fine

        # Upload new file
        StorageService.upload_file(
            StorageService.BUCKET_CVS,
            file_path,
            file_data,
            content_type
        )

        return file_path

    @staticmethod
    def upload_teacher_video(teacher_id: int, file_data: bytes, filename: str) -> str:
        """
        Upload teacher intro video and return storage path
        """
        extension = filename.split('.')[-1].lower()
        content_type_map = {
            'mp4': 'video/mp4',
            'mov': 'video/quicktime'
        }
        content_type = content_type_map.get(extension, 'video/mp4')

        file_path = f"{teacher_id}/intro.{extension}"

        # Delete old file if exists
        try:
            StorageService.delete_file(StorageService.BUCKET_VIDEOS, file_path)
        except:
            pass

        StorageService.upload_file(
            StorageService.BUCKET_VIDEOS,
            file_path,
            file_data,
            content_type
        )

        return file_path

    @staticmethod
    def upload_teacher_headshot(teacher_id: int, file_data: bytes, filename: str) -> str:
        """
        Upload teacher headshot photo and return storage path
        """
        extension = filename.split('.')[-1].lower()
        content_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png'
        }
        content_type = content_type_map.get(extension, 'image/jpeg')

        file_path = f"{teacher_id}/headshot.{extension}"

        # Delete old file if exists
        try:
            StorageService.delete_file(StorageService.BUCKET_PHOTOS, file_path)
        except:
            pass

        StorageService.upload_file(
            StorageService.BUCKET_PHOTOS,
            file_path,
            file_data,
            content_type
        )

        return file_path

    @staticmethod
    def get_teacher_cv_url(teacher_id: int, cv_path: str) -> str:
        """Get signed URL for teacher CV (1 hour expiry)"""
        return StorageService.get_signed_url(StorageService.BUCKET_CVS, cv_path, 3600)

    @staticmethod
    def get_teacher_video_url(teacher_id: int, video_path: str) -> str:
        """Get signed URL for teacher video (1 hour expiry)"""
        return StorageService.get_signed_url(StorageService.BUCKET_VIDEOS, video_path, 3600)

    @staticmethod
    def get_teacher_headshot_url(teacher_id: int, photo_path: str) -> str:
        """Get signed URL for teacher headshot (1 hour expiry)"""
        return StorageService.get_signed_url(StorageService.BUCKET_PHOTOS, photo_path, 3600)
