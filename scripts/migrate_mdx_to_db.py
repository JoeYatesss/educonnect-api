"""
Script to migrate existing MDX blog posts to database

This script reads MDX files from the educonnect-web content directory,
parses their frontmatter and content, converts markdown to HTML,
and inserts them into the blog_posts table.

Usage:
    python scripts/migrate_mdx_to_db.py

Requirements:
    pip install python-frontmatter markdown
"""

import os
import sys
import frontmatter
from supabase import create_client, Client
from datetime import datetime


# MDX files to migrate (located in educonnect-web/content/blog/)
MDX_FILES = [
    'first-month-shanghai.mdx',
    'cultural-differences.mdx',
    'expat-network.mdx',
    'career-progression.mdx',
    'technology-classrooms.mdx',
    'weekend-adventures.mdx'
]


def convert_markdown_to_html(markdown_content: str) -> str:
    """
    Convert markdown content to HTML

    Args:
        markdown_content: Raw markdown string

    Returns:
        HTML string
    """
    try:
        import markdown

        # Convert markdown to HTML with extensions
        html = markdown.markdown(
            markdown_content,
            extensions=[
                'extra',      # Tables, code blocks, etc.
                'nl2br',      # Newline to <br>
                'sane_lists', # Better list handling
            ]
        )

        return html
    except ImportError:
        print("ERROR: markdown library not installed. Run: pip install markdown")
        sys.exit(1)


def migrate_post(file_path: str, supabase: Client) -> dict:
    """
    Migrate a single MDX post to database

    Args:
        file_path: Path to MDX file
        supabase: Supabase client instance

    Returns:
        Dictionary with migration result
    """
    try:
        # Read and parse MDX file
        with open(file_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)

        # Extract slug from filename
        slug = os.path.basename(file_path).replace('.mdx', '')

        # Convert markdown content to HTML
        html_content = convert_markdown_to_html(post.content)

        # Prepare database record
        blog_data = {
            'title': post.get('title', ''),
            'slug': slug,
            'excerpt': post.get('excerpt', ''),
            'content': html_content,
            'category': post.get('category', 'Uncategorized'),
            'author': post.get('author', 'EduConnect Team'),
            'featured_image': post.get('image', ''),
            'is_published': True,
            'published_at': post.get('date', datetime.now().isoformat()),
        }

        # Insert into database
        result = supabase.table('blog_posts').insert(blog_data).execute()

        return {
            'success': True,
            'title': blog_data['title'],
            'slug': slug,
            'id': result.data[0]['id'] if result.data else None
        }

    except Exception as e:
        return {
            'success': False,
            'file': file_path,
            'error': str(e)
        }


def main():
    """Main migration function"""
    print("=" * 60)
    print("MDX to Database Migration Script")
    print("=" * 60)
    print()

    # Initialize Supabase client
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set")
        sys.exit(1)

    supabase: Client = create_client(supabase_url, supabase_key)

    # Determine content directory path
    # Assuming script is run from educonnect-api directory
    content_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        '..',
        'educonnect-web',
        'content',
        'blog'
    )

    # Normalize path
    content_dir = os.path.normpath(content_dir)

    print(f"Content directory: {content_dir}")

    if not os.path.exists(content_dir):
        print(f"ERROR: Content directory not found: {content_dir}")
        print("Please run this script from the educonnect-api directory")
        sys.exit(1)

    print(f"Found content directory")
    print()

    # Migrate each MDX file
    results = []
    for mdx_file in MDX_FILES:
        file_path = os.path.join(content_dir, mdx_file)

        if not os.path.exists(file_path):
            print(f"⚠️  SKIP: {mdx_file} (file not found)")
            results.append({
                'success': False,
                'file': mdx_file,
                'error': 'File not found'
            })
            continue

        print(f"Migrating: {mdx_file}...")
        result = migrate_post(file_path, supabase)
        results.append(result)

        if result['success']:
            print(f"✓ Success: {result['title']} (slug: {result['slug']}, id: {result['id']})")
        else:
            print(f"✗ Failed: {result.get('error', 'Unknown error')}")

        print()

    # Summary
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    successful = sum(1 for r in results if r['success'])
    failed = sum(1 for r in results if not r['success'])

    print(f"Total files: {len(MDX_FILES)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if failed > 0:
        print()
        print("Failed migrations:")
        for result in results:
            if not result['success']:
                print(f"  - {result.get('file', 'unknown')}: {result.get('error', 'unknown')}")

    print()
    print("Migration complete!")
    print()
    print("Next steps:")
    print("1. Verify posts in database: SELECT * FROM blog_posts;")
    print("2. Test blog pages at: http://localhost:3000/blog")
    print("3. Test admin interface at: http://localhost:3000/admin/blog")
    print("4. Archive MDX files to content/blog/archive/ if everything works")


if __name__ == '__main__':
    main()
