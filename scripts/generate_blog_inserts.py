"""
Generate SQL INSERT statements for blog posts from MDX files
This script reads MDX files and outputs SQL INSERT statements that can be executed via MCP tools
"""

import os
import sys
import frontmatter
import json

try:
    import markdown
except ImportError:
    print("ERROR: markdown library not installed. Run: pip install markdown")
    sys.exit(1)

# MDX files to migrate
MDX_FILES = [
    'first-month-shanghai.mdx',
    'cultural-differences.mdx',
    'expat-network.mdx',
    'career-progression.mdx',
    'technology-classrooms.mdx',
    'weekend-adventures.mdx'
]

def convert_markdown_to_html(markdown_content: str) -> str:
    """Convert markdown content to HTML"""
    html = markdown.markdown(
        markdown_content,
        extensions=[
            'extra',
            'nl2br',
            'sane_lists',
        ]
    )
    return html

def escape_sql_string(s: str) -> str:
    """Escape single quotes in SQL strings"""
    if s is None:
        return ''
    return s.replace("'", "''")

def main():
    # Determine content directory path
    content_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        '..',
        'educonnect-web',
        'content',
        'blog'
    )
    content_dir = os.path.normpath(content_dir)

    if not os.path.exists(content_dir):
        print(f"ERROR: Content directory not found: {content_dir}")
        sys.exit(1)

    print("-- SQL INSERT statements for blog posts")
    print("-- Generated from MDX files")
    print()

    for mdx_file in MDX_FILES:
        file_path = os.path.join(content_dir, mdx_file)

        if not os.path.exists(file_path):
            print(f"-- SKIP: {mdx_file} (file not found)")
            continue

        try:
            # Read and parse MDX file
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)

            # Extract slug from filename
            slug = os.path.basename(file_path).replace('.mdx', '')

            # Convert markdown content to HTML
            html_content = convert_markdown_to_html(post.content)

            # Prepare SQL INSERT
            title = escape_sql_string(post.get('title', ''))
            excerpt = escape_sql_string(post.get('excerpt', ''))
            content = escape_sql_string(html_content)
            category = escape_sql_string(post.get('category', 'Uncategorized'))
            author = escape_sql_string(post.get('author', 'EduConnect Team'))
            featured_image = escape_sql_string(post.get('image', ''))
            published_at = post.get('date', '2025-01-01')

            sql = f"""
INSERT INTO blog_posts (
    title, slug, excerpt, content, category, author,
    featured_image, is_published, published_at
) VALUES (
    '{title}',
    '{slug}',
    '{excerpt}',
    '{content}',
    '{category}',
    '{author}',
    '{featured_image}',
    true,
    '{published_at}'
);
"""
            print(sql)

        except Exception as e:
            print(f"-- ERROR processing {mdx_file}: {e}")

    print()
    print("-- End of SQL statements")

if __name__ == '__main__':
    main()
