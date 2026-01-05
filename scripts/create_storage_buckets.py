"""
Create required storage buckets in Supabase
Run this once to set up the storage infrastructure
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.supabase import get_supabase_client
from app.config import get_settings

def create_storage_buckets():
    """Create required storage buckets for teacher uploads"""
    settings = get_settings()
    supabase = get_supabase_client()

    buckets = [
        {
            "id": "cvs",
            "name": "cvs",
            "public": False,  # Private bucket - requires authentication
            "file_size_limit": 10485760,  # 10MB in bytes
            "allowed_mime_types": [
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ]
        },
        {
            "id": "intro-videos",
            "name": "intro-videos",
            "public": False,
            "file_size_limit": 104857600,  # 100MB in bytes
            "allowed_mime_types": [
                "video/mp4",
                "video/quicktime"
            ]
        },
        {
            "id": "headshot-photos",
            "name": "headshot-photos",
            "public": False,
            "file_size_limit": 10485760,  # 10MB in bytes
            "allowed_mime_types": [
                "image/jpeg",
                "image/png"
            ]
        }
    ]

    print("Creating storage buckets in Supabase...")
    print(f"Project URL: {settings.supabase_url}")
    print()

    for bucket_config in buckets:
        bucket_id = bucket_config["id"]
        try:
            # Try to create the bucket
            result = supabase.storage.create_bucket(
                bucket_id,
                options={
                    "public": bucket_config["public"],
                    "file_size_limit": bucket_config["file_size_limit"],
                    "allowed_mime_types": bucket_config["allowed_mime_types"]
                }
            )
            print(f"✅ Created bucket: {bucket_id}")
            print(f"   - Public: {bucket_config['public']}")
            print(f"   - Size limit: {bucket_config['file_size_limit'] / 1048576:.0f}MB")
            print(f"   - Allowed types: {', '.join(bucket_config['allowed_mime_types'])}")
            print()
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                print(f"ℹ️  Bucket already exists: {bucket_id}")
                print()
            else:
                print(f"❌ Error creating bucket {bucket_id}: {error_msg}")
                print()

    print("Storage bucket setup complete!")
    print()
    print("Note: If buckets couldn't be created via API, please create them manually:")
    print("1. Go to https://supabase.com/dashboard")
    print("2. Select your project")
    print("3. Go to Storage > Create new bucket")
    print("4. Create the following buckets with these settings:")
    print()
    for bucket_config in buckets:
        print(f"   Bucket: {bucket_config['id']}")
        print(f"   - Public: {bucket_config['public']}")
        print(f"   - File size limit: {bucket_config['file_size_limit'] / 1048576:.0f}MB")
        print()

if __name__ == "__main__":
    create_storage_buckets()
