# -*- coding: utf-8 -*-

import bugzilla

from django.conf import settings
from django.core.urlresolvers import reverse

from models import Waiver, WAIVER_TYPES, Bugzilla, ResultGroup

from covscanhub.other.shortcuts import get_or_none


def has_bugzilla(package, release):
    """
    return True if there is BZ created for specified package/release
    """
    return get_or_none(Bugzilla, package=package, release=release)


def get_unreported_bugs(package, release):
    """
    return IS_A_BUG waivers that weren't reported yet
    """
    rgs = ResultGroup.objects.select_related().filter(
        result__scanbinding__scan__package=package,
        result__scanbinding__scan__tag__release=release,
    )
    waivers = Waiver.objects.filter(
        result_group__result__scanbinding__scan__package=package,
        result_group__result__scanbinding__scan__tag__release=release,
        state=WAIVER_TYPES['IS_A_BUG'],
        bz__isnull=True,
        is_deleted=False,
        id__in=[rg.has_waiver().id for rg in rgs if rg.has_waiver()]
    )
    if waivers:
        return waivers.order_by('date')
    else:
        return None


def format_waivers(waivers, request):
    """
    return output of waivers/defects that is posted to bugzilla
    """
    comment = ''
    for w in waivers:
        comment += "Group: %s\nDate: %s\nMessage: %s\nLink: %s\n" % (
            w.result_group.checker_group.name,
            w.date.strftime('%Y-%m-%d %H:%M:%S %Z'),  # 2013-01-04 04:09:51 EST
            w.message,
            request.build_absolute_uri(
                reverse('waiving/waiver', args=(w.result_group.result.id,
                                                w.result_group.id))
            )
        )
        if w != waivers.reverse()[0]:
            comment += "-" * 80 + "\n\n"
    return comment


def get_checker_groups(waivers):
    s = ""
    for n in waivers.values('result_group__checker_group__name').distinct():
        s += "%s\n" % n['result_group__checker_group__name']
    return s



def create_bugzilla(request, package, release):
    """
    create bugzilla for package/release and fill it with all IS_A_BUG waivers
    this function should be called by view -- button "Create Bugzilla"
    """
    bz = bugzilla.Bugzilla(url=settings.BZ_URL,
                           user=settings.BZ_USER,
                           password=settings.BZ_PSWD)
    waivers = get_unreported_bugs(package, release)

    comment = """
Coverity has found defect(s) in package %s\n
== Reported groups ==
%s
== Notes ==
You may find waivers that you marked as bugs bellow. These records contain \
date, message and link to actual waiver.\n
If you have any questions, feel free to ask at #coverity or coverity-users@redhat.com\n
== Marked waivers ==
""" % (
    package.name,
    get_checker_groups(waivers)
    )

    summary = '[Coverity] %d waivers for %s' % (waivers.count(), release.tag)
    comment += format_waivers(waivers, request)

    data = {
        'product': release.product,
        'component': package.name,
        'summary': summary,  # 'short_desc'
        'version': release.get_prod_ver(),
        'comment': comment,
        'bug_severity': 'medium',
        'priority': 'high',
        'rep_platform': 'All',
        'op_sys': 'Linux',
    }
    # set bug as private?
    b = bz.createbug(**data)
    db_bz = Bugzilla()
    db_bz.release = release
    db_bz.package = package
    db_bz.number = b.bug_id
    db_bz.save()
    for w in waivers:
        w.bz = db_bz
        w.save()


def update_bugzilla(request, package, release):
    """
    add defects to specified bugzilla that aren't there yet
    this function should be called by view -- button "update bugzilla"
    """
    bz = bugzilla.Bugzilla(url=settings.BZ_URL,
                           user=settings.BZ_USER,
                           password=settings.BZ_PSWD)
    db_bz = has_bugzilla(package, release)
    if db_bz:
        waivers = get_unreported_bugs(package, release)
        comment = format_waivers(waivers, request)
        bzbug = bz.getbug(db_bz.number)
        bzbug.addcomment(comment, False)
        for w in waivers:
            w.bz = db_bz
            w.save()
    else:
        create_bugzilla(package, release)