# -*- coding: utf-8 -*-
"""
Utility functions.

License: BSD

(c) 2007 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import datetime
import calendar

from trac.util.datefmt import utc
from trac.util.text import to_unicode


def add_months(thedate, months):
    """ Add <months> months to <thedate>. """
    y, m, d = thedate.timetuple()[:3]
    y2, m2 = divmod(m + months - 1, 12)
    return datetime.datetime(y + y2, m2 + 1, d, tzinfo=thedate.tzinfo)

def map_month_names(month_list):
    """ Returns a list containing the 12 month names. """
    if len(month_list) == 12:
        # A list of 12 names is passed in, use that
        return month_list
    else:
        # Use list from default locale setting
        return [to_unicode(calendar.month_name[i+1]) for i in range(12)]

def parse_period(items=[]):
    """ Parses a list of items for elements of dates, and returns
    a month as (from_dt, to_dt) if valid. (None, None) if not. """
    if not len(items) == 2:
        return None, None
    try:
        # Test for year and month values
        year = int(items[0])
        month = int(items[1])
        from_dt = datetime.datetime(year, month, 1, tzinfo=utc)
        to_dt = add_months(from_dt, months=1)
    except ValueError:
        # Not integers, ignore
        to_dt = from_dt = None
    return from_dt, to_dt
