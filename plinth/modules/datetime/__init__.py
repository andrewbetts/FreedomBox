#
# This file is part of FreedomBox.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
FreedomBox app to configure system date and time.
"""

import subprocess

from django.utils.translation import ugettext_lazy as _

from plinth import service as service_module
from plinth.menu import main_menu

from .manifest import backup

version = 2

is_essential = True

managed_services = ['systemd-timesyncd']

managed_packages = []

name = _('Date & Time')

description = [
    _('Network time server is a program that maintains the system time '
      'in synchronization with servers on the Internet.')
]

manual_page = 'DateTime'

service = None


def init():
    """Intialize the date/time module."""
    menu = main_menu.get('system')
    menu.add_urlname(name, 'fa-clock-o', 'datetime:index')

    global service
    setup_helper = globals()['setup_helper']
    if setup_helper.get_state() != 'needs-setup':
        service = service_module.Service(managed_services[0], name,
                                         is_external=True)


def setup(helper, old_version=None):
    """Install and configure the module."""
    global service
    if service is None:
        service = service_module.Service(managed_services[0], name,
                                         is_external=True)
    service.enable()
    helper.call('post', service.notify_enabled, None, True)


def diagnose():
    """Run diagnostics and return the results."""
    results = []
    results.append(_diagnose_time_synchronized())

    return results


def _diagnose_time_synchronized():
    """Check whether time is synchronized to NTP server."""
    result = 'failed'
    try:
        output = subprocess.check_output(
            ['timedatectl', 'show', '--property=NTPSynchronized', '--value'])
        if 'yes' in output.decode():
            result = 'passed'
    except subprocess.CalledProcessError:
        pass

    return [_('Time synchronized to NTP server'), result]
