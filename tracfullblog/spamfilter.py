# -*- coding: utf-8 -*-
"""
Spam filter adapter.

License: BSD

(c) 2007 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

from trac.core import *
from trac.resource import Resource
from trac.util import arity
from trac.util.compat import set
from trac.util.text import to_unicode
from tracspamfilter.api import FilterSystem
from tracfullblog.api import IBlogManipulator
from tracfullblog.model import BlogPost


class BlogSpamFilterAdapter(Component):
    """Pass blog posts and comments through the spam filter."""

    implements(IBlogManipulator)

    # IBlogManipulator methods

    def validate_blog_post(self, req, postname, version, fields):
        if 'blog-preview' in req.args:
            return []

        blog_res = Resource('blog', postname, version)
        if req.perm(blog_res).has_permission('BLOG_ADMIN'):
            return []

        if version > 1:
            bp = BlogPost(self.env, postname, version)
            last_post_fields = bp._fetch_fields(version=version-1)
        else:
            last_post_fields = {}

        field_names = set(fields).union(last_post_fields)
        changes = []
        for field in field_names:
            old = to_unicode(last_post_fields.get(field, ''))
            new = to_unicode(fields.get(field, ''))
            if new and old != new:
                changes.append((old, new))
        author = fields.get('author', '')
        if arity(FilterSystem.test) == 4:
            # 0.11 compatible method signature
            FilterSystem(self.env).test(req, author, changes)
        else:
            # 0.12+ compatible that adds an 'ip' argument
            FilterSystem(self.env).test(req, author, changes, req.remote_addr)
        return []

    def validate_blog_comment(self, req, postname, fields):
        if 'previewcomment' in req.args:
            return []

        blog_res = Resource('blog', postname)
        if req.perm(blog_res).has_permission('BLOG_ADMIN'):
            return []

        author = fields.get('author', '')
        changes = [(None, fields.get('comment', '')),
                   (None, author)]
        if arity(FilterSystem.test) == 4:
            # 0.11 compatible method signature
            FilterSystem(self.env).test(req, author, changes)
        else:
            # 0.12+ compatible that adds an 'ip' argument
            FilterSystem(self.env).test(req, author, changes, req.remote_addr)
        return []
