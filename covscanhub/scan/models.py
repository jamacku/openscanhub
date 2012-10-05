# -*- coding: utf-8 -*-


from django.db import models
from kobo.hub.models import Task
from kobo.types import Enum

SCAN_STATES = Enum(
    "QUEUED",            # scan was submitted, waiting for scheduler
    "SCANNING",          # scan/task is active now
    "NEEDS_INSPECTION",  # scan finished and there are some unwaived things
    "WAIVED",            # scan finished and everything is okay -- waived
    "PASSED",            # nothing new
    "FINISHED",          # scan finished -- USER scans only
)

SCAN_TYPES = Enum(
    "ERRATA",           # this scan was submitted from ET
    "USER",             # some user posted this scan
)


class MockConfig(models.Model):
    name        = models.CharField(max_length=256, unique=True)
    enabled     = models.BooleanField(default=True)

    class Meta:
        ordering = ("name", )

    def __unicode__(self):
        return self.name

    def export(self):
        result = {
            "name": self.name,
            "enabled": self.enabled,
        }
        return result


class Tag(models.Model):
    """
    This class stores information about tags from brew and mapping between
    these tags and mock configs
    """

    name = models.CharField("Brew Tag", max_length=64, blank=False)
    mock = models.ForeignKey(MockConfig, verbose_name="Mock Config",
                             blank=False, null=False)

    def __unicode__(self):
        return "%s <-> %s" % (self.name, str(self.mock))


class Scan(models.Model):
    """
    #This class stores information about differential scans
    """
    #yum-3.4.3-42.el7
    #name-version-release of scanned package
    nvr = models.CharField("NVR", max_length=512,
                           blank=False, help_text="Name-Version-Release")

    scan_type = models.PositiveIntegerField(default=SCAN_TYPES["ERRATA"],
                                            choices=SCAN_TYPES.get_mapping(),
                                            help_text="Scan Type")

    #information for differential scan -- which version of package we are
    #diffing to
    base = models.ForeignKey('self', verbose_name="Base Scan",
                             blank=True, null=True,
                             help_text="NVR of package to diff against")
    #user scans dont have to specify this option -- allow None
    tag = models.ForeignKey(Tag, verbose_name="Tag",
                            blank=True, null=True,
                            help_text="Tag from brew")
    task = models.ForeignKey(Task, verbose_name="Asociated Task",
                             help_text="Asociated task on worker")
    state = models.PositiveIntegerField(default=SCAN_STATES["QUEUED"],
                                        choices=SCAN_STATES.get_mapping(),
                                        help_text="Current scan state")
    # string containing user's name who is responsible for scan
    username = models.CharField("Username", max_length=32, blank=True,
                                null=True,)

    #defects count
    #defects information

    def __unicode__(self):
        if self.base is None:
            return u"#%s [%s]" % (self.id, self.nvr)
        else:
            return u"#%s [%s <-> %s]" % (self.id, self.nvr, self.base.nvr)

    def is_errata_scan(self):
        return self.scan_type == SCAN_TYPES['ERRATA']

    def is_user_scan(self):
        return self.scan_type == SCAN_TYPES['USER']

    @classmethod
    def create_scan(cls, scan_type, nvr, tag, task_id, username, base=None):
        scan = cls()
        scan.scan_type = scan_type
        scan.nvr = nvr
        scan.base = base
        scan.tag = tag
        scan.task = Task.objects.get(id=task_id)
        scan.state = SCAN_STATES["QUEUED"]
        scan.username = username
        scan.save()
        return scan