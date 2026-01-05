"""
Script to create admin user via Supabase Admin API

Usage:
    python scripts/create_admin_user.py --email admin@educonnect.com --password <password> --name "Admin User"

Requirements:
    - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set
"""

import os
import argparse
from supabase import create_client, Client


def create_admin_user(email: str, password: str, full_name: str) -> None:
    """
    Create an admin user in Supabase authentication and admin_users table

    Args:
        email: Admin email address
        password: Admin password
        full_name: Admin full name
    """
    # Get Supabase credentials from environment
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not supabase_url or not supabase_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set"
        )

    # Initialize Supabase client with service role key
    supabase: Client = create_client(supabase_url, supabase_key)

    print(f"Creating admin user for email: {email}")

    try:
        # Create authentication user
        auth_response = supabase.auth.admin.create_user({
            'email': email,
            'password': password,
            'email_confirm': True  # Auto-confirm email
        })

        user_id = auth_response.user.id
        print(f"✓ Auth user created with ID: {user_id}")

        # Create admin record in admin_users table
        admin_data = {
            'id': user_id,
            'full_name': full_name,
            'role': 'admin',
            'is_active': True
        }

        result = supabase.table('admin_users').insert(admin_data).execute()
        print(f"✓ Admin record created in admin_users table")

        print("\n" + "="*60)
        print("Admin user created successfully!")
        print("="*60)
        print(f"Email:    {email}")
        print(f"Name:     {full_name}")
        print(f"User ID:  {user_id}")
        print(f"Role:     admin")
        print(f"Status:   active")
        print("="*60)
        print("\nYou can now log in to the admin dashboard at /admin")

    except Exception as e:
        print(f"\n✗ Error creating admin user: {str(e)}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Create an admin user for EduConnect platform'
    )
    parser.add_argument(
        '--email',
        required=True,
        help='Admin email address'
    )
    parser.add_argument(
        '--password',
        required=True,
        help='Admin password (minimum 6 characters)'
    )
    parser.add_argument(
        '--name',
        required=True,
        help='Admin full name'
    )

    args = parser.parse_args()

    # Validate password length
    if len(args.password) < 6:
        print("Error: Password must be at least 6 characters long")
        return

    create_admin_user(args.email, args.password, args.name)


if __name__ == '__main__':
    main()
