# -*- coding: utf-8 -*-
"""
Provider for Tags plugin.

License: BSD

(c) 2007 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

from trac.core import *
from tractags.api import ITagProvider
from trac.util.compat import set
from trac.resource import Resource, get_resource_description
from trac.web.chrome import Chrome

from model import BlogPost, _parse_categories


class FullBlogTagSystem(Component):
    implements(ITagProvider)

    # ITagProvider methods
    def get_taggable_realm(self):
        return 'blog'

    def get_tagged_resources(self, req, tags):
        if 'TAGS_VIEW' not in req.perm or 'BLOG_VIEW' not in req.perm:
            return

        db = self.env.get_db_cnx()
        cursor = db.cursor()

        args = []
        constraints = []
        sql = "SELECT bp1.name, bp1.categories, bp1.version " \
               "FROM fullblog_posts bp1," \
               "(SELECT name, max(version) AS ver " \
               "FROM fullblog_posts GROUP BY name) bp2 " \
               "WHERE bp1.version = bp2.ver AND bp1.name = bp2.name"
        if tags:
            constraints.append("(" + ' OR '.join(
                            ["bp1.categories LIKE %s" for t in tags]) + ")")
            args += ['%' + t + '%' for t in tags]
        else:
            constraints.append("bp1.categories != ''")
        if constraints:
            sql += " AND " + " AND ".join(constraints)
        sql += " ORDER BY bp1.name"
        self.env.log.debug(sql)
        cursor.execute(sql, args)
        for row in cursor:
            post_name, categories = row[0], set(_parse_categories(row[1]))
            if not tags or categories.intersection(tags):
                resource = Resource('blog', post_name)
                if 'BLOG_VIEW' in req.perm(resource) and \
                        'TAGS_VIEW' in req.perm(resource):
                    yield (resource, categories)

    def get_resource_tags(self, req, resource):
        req.perm(resource).require('BLOG_VIEW')
        req.perm(resource).require('TAGS_VIEW')
        return BlogPost(self.env, resource.id).category_list

    def set_resource_tags(self, req, resource, tags):
        req.perm(resource).require('TAGS_MODIFY')
        post = BlogPost(self.env, resource.id)
        if post.author == req.authname:
            req.perm(resource).require('BLOG_MODIFY_OWN')
        else:
            req.perm(resource).require('BLOG_MODIFY_ALL')
        post.categories = " ".join(tags)
        post.save(req.authname, 'Blog post categories changed via Tags plugin.')

    def remove_resource_tags(self, req, resource):
        req.perm(resource).require('TAGS_MODIFY')
        post = BlogPost(self.env, resource.id)
        if post.author == req.authname:
            req.perm(resource).require('BLOG_MODIFY_OWN')
        else:
            req.perm(resource).require('BLOG_MODIFY_ALL')
        post.categories = ""
        post.save(req.authname, 'Blog post categories removed via Tags plugin.')

    def describe_tagged_resource(self, req, resource):
        # The plugin already uses the title as main description
        post = BlogPost(self.env, resource.id)
        chrome = Chrome(self.env)
        return "'" + resource.id + "' by " \
                                    + chrome.format_author(req, post.author)
