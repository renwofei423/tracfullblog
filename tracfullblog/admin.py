# -*- coding: utf-8 -*-
"""
TracFullBlog admin panel for some settings related to the plugin.

License: BSD

(c) 2007 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

from trac.core import *
from trac.admin import IAdminPanelProvider
from trac.resource import Resource
from trac.web.chrome import add_warning

# Relative imports
from core import FullBlogCore

__all__ = ['FullBlogAdminPanel']

class FullBlogAdminPanel(Component):
    """ Admin panel for settings related to FullBlog plugin. """

    implements(IAdminPanelProvider)
    
    # IAdminPageProvider

    def get_admin_panels(self, req):
        if 'BLOG_ADMIN' in req.perm('blog'):
            yield ('blog', 'Blog', 'settings', 'Settings')

    def render_admin_panel(self, req, cat, page, path_info):     
        req.perm(Resource('blog', None)).require('BLOG_ADMIN')

        blog_admin = {}
        blog_core = FullBlogCore(self.env)
        
        if req.method == "POST":
            if req.args.get('savesettings'):
                self.env.config.set('fullblog', 'num_items_front',
                    int(req.args.get('numpostsfront')))
                self.env.config.set('fullblog', 'default_postname',
                    req.args.get('defaultpostname'))
                self.env.config.save()
            elif req.args.get('savebloginfotext'):
                self.env.log.debug("New blog info text = %r" % req.args.get('bloginfotext'))
                is_ok = blog_core.set_bloginfotext(
                        req.args.get('bloginfotext'))
                if is_ok:
                    req.redirect(req.href.admin(req.args['cat_id'],
                            req.args['panel_id']))
                else:
                    add_warning(req, "Error storing text in database. Not saved.")
            else:
                self.log.warning('Unknown POST request: %s', req.args)
        
        blog_admin['bloginfotext'] = blog_core.get_bloginfotext()
        blog_admin['numpostsfront'] = self.env.config.getint(
                                            'fullblog', 'num_items_front')
        blog_admin['defaultpostname'] = self.env.config.get(
                                            'fullblog', 'default_postname')
        
        return ('fullblog_admin.html', {'blog_admin': blog_admin})

