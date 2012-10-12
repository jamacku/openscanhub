# -*- coding: utf-8 -*-

import copy
import brew
import os

#import messaging.send_message
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from covscanhub.scan.service import prepare_and_execute_diff
from covscanhub.scan.models import Scan, SCAN_STATES, SCAN_TYPES, Tag
from covscanhub.waiving.service import create_results
from covscanhub.other.shortcuts import get_mock_by_name, check_brew_build, \
check_and_create_dirs
from kobo.hub.models import Task

            
def create_errata_base_scan(kwargs, task_id):
    options = {}

    task_user = kwargs['task_user']
    username = kwargs['username']
    scan_type = SCAN_TYPES['ERRATA_BASE']
    base_obj = None
    nvr = kwargs['base']
    task_label = nvr
    
    tag = kwargs['base_tag']
    
    priority = kwargs.get('priority', settings.ET_SCAN_PRIORITY) + 1
    comment = 'Errata Tool Base scan of %s requested by %s' % \
        (nvr, kwargs['base'])

    # Test if SRPM exists
    check_brew_build(nvr)

    #does tag exist?
    options['mock_config'] = get_mock_by_tag_name(tag).name
    tag_obj = Tag.objects.get(name=tag)

    task_id = Task.create_task(
        owner_name=task_user,
        label=task_label,
        method='ErrataDiffBuild',
        args={}, # I want to add scan's id here, so I update it later
        comment=comment,
        state=SCAN_STATES["QUEUED"],
        priority=priority,
        parent_id=task_id,
    )
    task_dir = Task.get_task_dir(task_id)

    check_and_create_dirs(task_dir)

    # if base is specified, try to fetch it; if it doesn't exist, create
    # new task for it
    scan = Scan.create_scan(scan_type=scan_type, nvr=nvr, task_id=task_id,
                            tag=tag_obj, base=base_obj, username=username)
    scan.save()

    options['scan_id'] = scan.id
    task = Task.objects.get(id=task_id)
    task.args = options
    task.save()
    
    return scan

def create_errata_scan(kwargs):
    """
    create scan of a package and perform diff on results against specified
    version
    options of this scan are in dict 'kwargs'

    kwargs
     - scan_type - type of scan (SCAN_TYPES in covscanhub.scan.models)
     - username - name of user who is requesting scan (from ET)
     - task_user - username from request.user.username
     - nvr - name, version, release of scanned package
     - base - previous version of package, the one to make diff against
     - id - errata ID
     - nvr_tag - tag of the package from brew
     - base_tag - tag of the base package from brew
     - rhel_version - version of enterprise linux in which will package appear
    """
    options = {}

    #from request.user
    task_user = kwargs['task_user']

    #supplied by scan initiator
    username = kwargs['username']
    scan_type = kwargs['scan_type']
    nvr = kwargs['nvr']
    base = kwargs['base']
    options['errata_id'] = kwargs['id']

    #Label, description or any reason for this task.
    task_label = nvr

    tag = kwargs['nvr_tag']
    priority = kwargs.get('priority', settings.ET_SCAN_PRIORITY)

    #if kwargs does not have 'id', it is base scan
    comment = 'Errata Tool Scan of %s' % nvr

    #does tag exist?
    options['mock_config'] = get_mock_by_tag_name(tag).name

    # Test if SRPM exists
    check_brew_build(nvr)

    task_id = Task.create_task(
        owner_name=task_user,
        label=task_label,
        method='ErrataDiffBuild',
        args={},  # I want to add scan's id here, so I update it later
        comment=comment,
        state=SCAN_STATES["QUEUED"],
        priority=priority,
    )
    task_dir = Task.get_task_dir(task_id)

    check_and_create_dirs(task_dir)

    # if base is specified, try to fetch it; if it doesn't exist, create
    # new task for it
    base_obj = None
    if base:
        try:
            base_obj = Scan.objects.get(nvr=base)
        except ObjectDoesNotExist:
            parent_task = Task.objects.get(id=task_id)            
            base_obj = create_errata_base_scan(copy.deepcopy(kwargs), task_id)

            # wait has to be after creation of new subtask
            # TODO wait should be executed in one transaction with creation of
            # child
            parent_task.wait()
        except MultipleObjectsReturned:
            #return latest, but this shouldnt happened
            base_obj = Scan.objects.filter(nvr=base).\
                order_by('-task__dt_finished')[0]

    scan = Scan.create_scan(scan_type=scan_type, nvr=nvr, task_id=task_id,
                            tag=tag_obj, base=base_obj, username=username)

    options['scan_id'] = scan.id
    task = Task.objects.get(id=task_id)
    task.args = options
    task.save()

    return scan    