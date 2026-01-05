-- Migration: Add Blog Posts Table
-- Description: Create blog_posts table with rich text content support
-- Author: EduConnect Platform
-- Date: 2026-01-04

-- Blog Posts Table
CREATE TABLE blog_posts (
  id BIGSERIAL PRIMARY KEY,

  -- Core Content
  title VARCHAR(500) NOT NULL,
  slug VARCHAR(255) UNIQUE NOT NULL,
  excerpt TEXT,
  content TEXT NOT NULL, -- Rich text stored as HTML
  content_json JSONB, -- Optional: TipTap JSON format for editing

  -- Metadata
  category VARCHAR(100),
  author VARCHAR(255) DEFAULT 'EduConnect Team',
  featured_image VARCHAR(500),

  -- Publishing
  is_published BOOLEAN DEFAULT false,
  published_at TIMESTAMPTZ,

  -- Admin tracking
  created_by UUID REFERENCES admin_users(id),
  updated_by UUID REFERENCES admin_users(id),

  -- SEO
  meta_description TEXT,
  meta_keywords TEXT[],

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_blog_posts_slug ON blog_posts(slug);
CREATE INDEX idx_blog_posts_is_published ON blog_posts(is_published);
CREATE INDEX idx_blog_posts_category ON blog_posts(category);
CREATE INDEX idx_blog_posts_published_at ON blog_posts(published_at DESC);
CREATE INDEX idx_blog_posts_created_at ON blog_posts(created_at DESC);

-- Updated_at trigger
CREATE TRIGGER update_blog_posts_updated_at
  BEFORE UPDATE ON blog_posts
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security
ALTER TABLE blog_posts ENABLE ROW LEVEL SECURITY;

-- Public can view published posts
CREATE POLICY "Public can view published blog posts"
  ON blog_posts FOR SELECT
  USING (is_published = true);

-- Admins can manage all posts
CREATE POLICY "Admins can manage blog posts"
  ON blog_posts FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Comments
COMMENT ON TABLE blog_posts IS 'Blog posts with rich text content managed by admins';
COMMENT ON COLUMN blog_posts.content IS 'HTML content for public display';
COMMENT ON COLUMN blog_posts.content_json IS 'TipTap JSON format for rich editing';
COMMENT ON COLUMN blog_posts.slug IS 'URL-friendly identifier';
COMMENT ON COLUMN blog_posts.is_published IS 'Whether post is publicly visible';
