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
FreedomBox app to configure a Deluge web client.
"""

from django.utils.translation import ugettext_lazy as _

from plinth import action_utils, actions
from plinth import app as app_module
from plinth import frontpage, menu
from plinth.daemon import Daemon
from plinth.modules.apache.components import Webserver
from plinth.modules.firewall.components import Firewall
from plinth.modules.users import register_group

from .manifest import backup, clients  # noqa, pylint: disable=unused-import

version = 3

managed_services = ['deluge-web']

managed_packages = ['deluged', 'deluge-web']

name = _('Deluge')

short_description = _('BitTorrent Web Client')

description = [
    _('Deluge is a BitTorrent client that features a Web UI.'),
    _('When enabled, the Deluge web client will be available from '
      '<a href="/deluge" data-turbolinks="false">/deluge</a> path on the web '
      'server. The default password is \'deluge\', but you should log in and '
      'change it immediately after enabling this service.')
]

group = ('bit-torrent', _('Download files using BitTorrent applications'))

reserved_usernames = ['debian-deluged']

clients = clients

manual_page = 'Deluge'

app = None


class DelugeApp(app_module.App):
    """FreedomBox app for Deluge."""

    app_id = 'deluge'

    def __init__(self):
        """Create components for the app."""
        super().__init__()
        menu_item = menu.Menu('menu-deluge', name, short_description, 'deluge',
                              'deluge:index', parent_url_name='apps')
        self.add(menu_item)

        shortcut = frontpage.Shortcut(
            'shortcut-deluge', name, short_description=short_description,
            url='/deluge', icon='deluge', clients=clients, login_required=True,
            allowed_groups=[group[0]])
        self.add(shortcut)

        firewall = Firewall('firewall-deluge', name, ports=['http', 'https'],
                            is_external=True)
        self.add(firewall)

        webserver = Webserver('webserver-deluge', 'deluge-plinth')
        self.add(webserver)

        daemon = Daemon('daemon-deluge', managed_services[0])
        self.add(daemon)


def init():
    """Initialize the Deluge module."""
    global app
    app = DelugeApp()
    register_group(group)

    setup_helper = globals()['setup_helper']
    if setup_helper.get_state() != 'needs-setup' and app.is_enabled():
        app.set_enabled(True)


def setup(helper, old_version=None):
    """Install and configure the module."""
    helper.install(managed_packages)
    helper.call('post', actions.superuser_run, 'deluge', ['setup'])
    helper.call('post', app.enable)


def diagnose():
    """Run diagnostics and return the results."""
    results = []

    results.append(action_utils.diagnose_port_listening(8112, 'tcp4'))
    results.append(action_utils.diagnose_port_listening(8112, 'tcp6'))
    results.extend(
        action_utils.diagnose_url_on_all('https://{host}/deluge',
                                         check_certificate=False))

    return results
