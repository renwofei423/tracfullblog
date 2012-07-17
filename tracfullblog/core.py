# -*- coding: utf-8 -*-
"""
TracFullBlog module with core components and functionality
shared across the various access interfaces and modules:
 * Permissions
 * Settings

License: BSD

(c) 2007 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

from time import strftime

from genshi.builder import tag

from trac.attachment import ILegacyAttachmentPolicyDelegate
from trac.core import *
from trac.config import Option
from trac.perm import IPermissionRequestor
from trac.resource import IResourceManager
from trac.util.compat import sorted, set
from trac.util.text import unicode_unquote
from trac.util.datefmt import to_datetime, utc
from trac.wiki.api import IWikiSyntaxProvider

# Relative imports (same package)
from api import IBlogChangeListener, IBlogManipulator
from model import BlogPost, get_blog_resources, get_blog_posts, get_all_blog_posts
from util import parse_period

import cache

class FullBlogCore(Component):
    """ Module implementing features that are common and shared
    between the various parts of the plugin. """

    # Extensions
    
    listeners = ExtensionPoint(IBlogChangeListener)
    manipulators = ExtensionPoint(IBlogManipulator)
    
    implements(IPermissionRequestor, IWikiSyntaxProvider, IResourceManager,
            ILegacyAttachmentPolicyDelegate)

    # Options

    Option('fullblog', 'default_postname', '',
        """Option for a default naming scheme for new posts. The string
        can include substitution markers for time (UTC) and user: %Y=year,
        %m=month, %d=day, %H=hour, %M=minute, %S=second, $USER.
        Example template string: `%Y/%m/%d/my_topic`""")

    # Constants

    reserved_names = ['create', 'view', 'edit', 'delete',
                    'archive', 'category', 'author']

    def __init__(self):
        self.env.systeminfo.append(('FullBlog',
                __import__('tracfullblog', ['__version__']).__version__))

    # IPermissionRequestor method
    
    def get_permission_actions(self):
        """ Permissions supported by the plugin.
        Commenting needs special enabling if wanted as it is only enabled
        if user is ADMIN or if specifically given BLOG_COMMENT permission.
        Apart from that, the permisions follow regular practice of builing
        on top of each other. """
        return ['BLOG_VIEW',
                ('BLOG_COMMENT', ['BLOG_VIEW']),
                ('BLOG_CREATE', ['BLOG_VIEW']),
                ('BLOG_MODIFY_OWN', ['BLOG_CREATE']),
                ('BLOG_MODIFY_ALL', ['BLOG_MODIFY_OWN']),
                ('BLOG_ADMIN', ['BLOG_MODIFY_ALL', 'BLOG_COMMENT']),
                ]

    # ILegacyAttachmentPolicyDelegate methods
    
    def check_attachment_permission(self, action, username, resource, perm):
        """ Respond to the various actions into the legacy attachment
        permissions used by the Attachment module. """
        if resource.parent.realm == 'blog':
            if action == 'ATTACHMENT_VIEW':
                return 'BLOG_VIEW' in perm(resource.parent)
            if action in ['ATTACHMENT_CREATE', 'ATTACHMENT_DELETE']:
                if 'BLOG_MODIFY_ALL' in perm(resource.parent):
                    return True
                elif 'BLOG_MODIFY_OWN' in perm(resource.parent):
                    bp = BlogPost(self.env, resource.parent.id)
                    if bp.author == username:
                        return True
                    else:
                        return False
                else:
                    return False

    # IResourceManager methods
    
    def get_resource_realms(self):
        yield 'blog'

    def get_resource_url(self, resource, href, **kwargs):
        return href.blog(resource.id,
                resource.version and 'version=%d' % (resource.version) or None)
        
    def get_resource_description(self, resource, format=None, context=None,
                                 **kwargs):
        bp = BlogPost(self.env, resource.id, resource.version)
        if context:
            return tag.a('Blog: '+bp.title, href=context.href.blog(resource.id))
        else:
            return 'Blog: '+bp.title

    def resource_exists(self, resource):
        bp = BlogPost(self.env, resource.id)
        return len(bp.versions)

    # IWikiSyntaxProvider methods

    def get_wiki_syntax(self):
        return []
    
    def get_link_resolvers(self):
        yield ('blog', self._bloglink_formatter)
    
    def _bloglink_formatter(self, formatter, ns, content, label):
        content = (content.startswith('/') and content[1:]) or content
        path_parts = [part for part in content.split('/') if part != '']
        if not content:
            return tag.a(label, href=formatter.href.blog(content))
        if len(path_parts) == 2 and path_parts[0].isdigit() \
                                and path_parts[1].isdigit():
            # Requesting a period listing
            return tag.a(label, href=formatter.href.blog(content))
        elif len(path_parts) and path_parts[0] in self.reserved_names:
            # Requesting a specific path to command or listing
            return tag.a(label, href=formatter.href.blog(content))
        else:
            # Assume it is a regular post, and pass to 'view'
            # Split for comment linking (the_post#comment-1, or #comment-1)
            segments = content.split('#')
            if len(segments) == 2:
                url, anchor = segments
            else:
                url = segments[0]
                anchor = ''
            return tag.a(label, href=(url and formatter.href.blog(url) or '') \
                    + (anchor and '#' + anchor or ''))

    # Utility methods used by other modules
    
    def get_bloginfotext(self):
        """ Retrieves the blog info text in sidebar from database. """
        try:
            cnx = self.env.get_db_cnx()
            cursor = cnx.cursor()
            cursor.execute("SELECT value from system " \
                "WHERE name='fullblog_infotext'")
            rows = cursor.fetchall()
            if rows:
                return rows[0][0] # Only item in cursor (hopefully)
            else:
                return ''
        except:
            return ''

    def set_bloginfotext(self, text=''):
        """ Stores the blog info text in the database. """
        try:
            cnx = self.env.get_db_cnx()
            cursor = cnx.cursor()
            cursor.execute("UPDATE system set value=%s " \
                "WHERE name=%s", (text, 'fullblog_infotext'))
            cnx.commit()
            return True
        except:
            return False
    
    def get_prev_next_posts(self, perm, post_name):
        """ Returns the name of the next and previous posts when compared with
        input 'post_name'. """
        prev = next = marker = ''
        found = False
        for post in get_blog_resources(self.env):
            if not 'BLOG_VIEW' in perm(post):
                continue
            if post.id == post_name:
                next = marker
                found = True
                continue
            if found:
                prev = post.id
                break
            marker = post.id
        return prev, next

    # CRUD methods that support input verification and listener and manipulator APIs
    
    def create_post(self, req, bp, version_author, version_comment=u'', verify_only=False):
        """ Creates a new post, or a new version of existing post.
        Does some input verification.
        Supports manipulator and listener plugins.
        Returns [] for success, or a list of (field, message) tuples if not."""
        warnings = []
        # Do basic checking for content existence
        warnings.extend(bp.save(version_author, version_comment, verify_only=True))
        # Make sure name for the post is a valid name
        warnings.extend(self._check_new_postname(req, bp.name))
        # Check if any plugins has objections with the contents
        fields = {
            'title': bp.title,
            'body': bp.body,
            'author': bp.author,
            'version_comment': version_comment,
            'version_author': version_author,
            'categories': bp.categories,
            'category_list': bp.category_list}
        for manipulator in self.manipulators:
            warnings.extend(manipulator.validate_blog_post(
                            req, bp.name, bp.version, fields))
        if warnings or verify_only:
            return warnings
        # All seems well - save and notify
        warnings.extend(bp.save(version_author, version_comment))
        for listener in self.listeners:
            listener.blog_post_changed(bp.name, bp.version)
        return warnings
        
    def delete_post(self, bp, version=0):
        """ Deletes a blog post (version=0 for all versions, or specific version=N).
        Notifies listeners if successful.
        Returns [] for success, or a list of (field, message) tuples if not."""
        warnings = []
        fields = bp._fetch_fields(version)
        if not fields:
            warnings.append(('', "Post and/or version does not exist."))
        # Inital checking. Return if there are problems.
        if warnings:
            return warnings
        # Do delete
        is_deleted = bp.delete(version)
        if not is_deleted:
            warnings.append(('', "Unknown error. Not deleted."))
        if is_deleted:
            version = bp.get_versions() and fields['version'] or 0 # Any versions left?
            for listener in self.listeners:
                    listener.blog_post_deleted(bp.name, version, fields)
                    if not version: # Also notify that all comments are deleted
                        listener.blog_comment_deleted(bp.name, 0, {})
        return warnings
    
    def create_comment(self, req, bc, verify_only=False):
        """ Create a comment. Comment and author set on the bc (comment) instance:
        * Calls manipulators and bc.create() (if not verify_only) collecting warnings
        * Calls listeners on success
        Returns [] for success, or a list of (field, message) tuples if not."""
        # Check for errors
        warnings = []
        # Verify the basics such as content existence, duplicates, post existence
        warnings.extend(bc.create(verify_only=True))
        # Now test plugins to see if new issues are raised.
        fields = {'comment': bc.comment,
                  'author': bc.author}
        for manipulator in self.manipulators:
            warnings.extend(
                manipulator.validate_blog_comment(req, bc.post_name, fields))
        if warnings or verify_only:
            return warnings
        # No problems (we think), try to save.
        warnings.extend(bc.create())
        if not warnings:
            for listener in self.listeners:
                listener.blog_comment_added(bc.post_name, bc.number)
        return warnings
    
    def delete_comment(self, bc):
        """ Deletes the comment (bc), and notifies listeners.
        Returns [] for success, or a list of (field, message) tuples if not."""
        warnings = []
        fields = {'post_name': bc.post_name,
                  'number': bc.number,
                  'comment': bc.comment,
                  'author': bc.author,
                  'time': bc.time}
        is_deleted = bc.delete()
        if is_deleted:
            for listener in self.listeners:
                listener.blog_comment_deleted(
                        fields['post_name'], fields['number'], fields)
        else:
            warnings.append(('', "Unknown error. Not deleted."))
        return warnings

    def get_months_authors_categories(self, from_dt=None, to_dt=None,
                                                user=None, perm=None):
        """ Returns a structure of post metadata:
            ([ ((year1, month1), count), ((year1, month2), count) ], # newest first
             [ (author1, count), (author2, count) ],                 # alphabetical
             [ (category1, count), (category2, count) ],             # alphabetical
             total)                                                  # num of posts
        * Use 'from_dt' and 'to_dt' (datetime objects) to restrict search to
        posts with a publish_time within the intervals (None means ignore).
        * If user and perm is provided, the list is also filtered for permissions.
        * Note also that it only fetches from most recent version. """
#        cache_months_authors_categories= self.env.project_name + "_months_authors_categories"
        cache_months_authors_categories = self.env.project_name + '_blog_posts_months'
#        if  user:
#            cache_months_authors_categories += "_user_" + user
        if  from_dt:   
            s_from_dt = str(from_dt)
            cache_months_authors_categories += s_from_dt.replace(" ", "").replace(":", "").replace("-", "").replace("+", "")
        if  to_dt:        
             s_to_dt= str(to_dt)
             cache_months_authors_categories += s_to_dt.replace(" ", "").replace(":", "").replace("-", "").replace("+", "")       
            
        if cache.c(cache_months_authors_categories):
            self.env.log.debug("%r  found Cache ,return Cache...318......." % cache_months_authors_categories)       
            return cache.c(cache_months_authors_categories)
        else:
            self.env.log.debug("%r not found. Cacheing.. 322." % cache_months_authors_categories)
            
            blog_posts = get_all_blog_posts(self.env, from_dt=from_dt, to_dt=to_dt)
            a_dict = {}
            c_dict = {}
            m_dict = {}
            total = 0
            for post in blog_posts:
                if user and perm:
                    # Check permissions
                    bp = BlogPost(self.env, post[0], post[1])
                    if not 'BLOG_VIEW' in perm(bp.resource):
                        continue # Skip this post
                post_time = post[2]
                m_dict[(post_time.year, post_time.month)] = m_dict.get(
                        (post_time.year, post_time.month), 0) + 1
                author = post[3]
                a_dict[author] = a_dict.get(author, 0) + 1
                categories = post[6] # a list
                for category in set(categories):
                    c_dict[category] = c_dict.get(category, 0) + 1
                total += 1
            return cache.c(cache_months_authors_categories,([(m, m_dict.get(m, 0)) for m in sorted(m_dict.keys(), reverse=True)],
                    [(a, a_dict.get(a, 0)) for a in sorted(a_dict.keys())],
                    [(c, c_dict.get(c, 0)) for c in sorted(c_dict.keys())],
                    total))
#            return cache.months_authors_categories

    # Internal methods
    
    def _get_default_postname(self, user=''):
        """ Parses and returns the setting for default_postname. """
        opt = self.env.config.get('fullblog', 'default_postname')
        if not opt:
            return ''
        # Perform substitutions
        try:
            now = to_datetime(None, utc).timetuple()
            name = strftime(opt, now)
            name = name.replace('$USER', user)
            return name
        except:
            self.env.log.debug(
                "FullBlog: Error parsing default_postname option: %s" % opt)
            return ''

    def _check_new_postname(self, req, name):
        """ Does some checking on the postname to make sure it does
        not conflict with existing commands. """
        warnings = []
        name = name.lower()
        # Reserved names
        for rn in self.reserved_names:
            if name == rn:
                warnings.append(('',
                    "'%s' is a reserved name. Please change." % name))
            if name.startswith(rn + '/'):
                warnings.append(('',
                    "Name cannot start with a reserved name as first item in "
                    "path ('%s'). Please change." % rn))
        # Check to see if it is a date range
        items = name.split('/')
        if len(items) == 2 and parse_period(items) != (None, None):
            warnings.append(('',
                "'%s' is seen as a time period, and cannot "
                "be used as a name. Please change." % name))        
        return warnings
