# SPDX-License-Identifier: AGPL-3.0-or-later
"""
FreedomBox app to configure minidlna.
"""
from django.utils.translation import gettext_lazy as _

from plinth import actions
from plinth import app as app_module
from plinth import frontpage, menu
from plinth.daemon import Daemon
from plinth.modules.apache.components import Webserver
from plinth.modules.backups.components import BackupRestore
from plinth.modules.firewall.components import Firewall
from plinth.modules.users.components import UsersAndGroups
from plinth.package import Packages, install
from plinth.utils import Version

from . import manifest

_description = [
    _('MiniDLNA is a simple media server software, with the aim of being '
      'fully compliant with DLNA/UPnP-AV clients. '
      'The MiniDLNA daemon serves media files '
      '(music, pictures, and video) to clients on a network. '
      'DLNA/UPnP is zero configuration protocol and is compliant '
      'with any device passing the DLNA Certification like portable '
      'media players, Smartphones, Televisions, and gaming systems ('
      'such as PS3 and Xbox 360) or applications such as totem and Kodi.')
]


class MiniDLNAApp(app_module.App):
    """Freedombox app managing miniDlna"""
    app_id = 'minidlna'

    _version = 2

    def __init__(self):
        """Initialize the app components"""
        super().__init__()

        groups = {'minidlna': _('Media streaming server')}

        info = app_module.Info(app_id=self.app_id, version=self._version,
                               name=_('MiniDLNA'), icon_filename='minidlna',
                               short_description=_('Simple Media Server'),
                               description=_description,
                               manual_page='MiniDLNA',
                               clients=manifest.clients)
        self.add(info)

        menu_item = menu.Menu(
            'menu-minidlna',
            name=info.name,
            short_description=info.short_description,
            url_name='minidlna:index',
            parent_url_name='apps',
            icon=info.icon_filename,
        )
        self.add(menu_item)

        shortcut = frontpage.Shortcut('shortcut-minidlna', info.name,
                                      short_description=info.short_description,
                                      description=info.description,
                                      icon=info.icon_filename,
                                      url='/_minidlna/', login_required=True,
                                      allowed_groups=list(groups))
        self.add(shortcut)

        packages = Packages('packages-minidlna', ['minidlna'])
        self.add(packages)

        firewall = Firewall('firewall-minidlna', info.name, ports=['minidlna'],
                            is_external=False)
        self.add(firewall)

        webserver = Webserver('webserver-minidlna', 'minidlna-freedombox',
                              urls=['http://localhost:8200/'])
        self.add(webserver)

        daemon = Daemon('daemon-minidlna', 'minidlna')
        self.add(daemon)

        backup_restore = BackupRestore('backup-restore-minidlna',
                                       **manifest.backup)
        self.add(backup_restore)

        users_and_groups = UsersAndGroups('users-and-groups-minidlna',
                                          groups=groups)
        self.add(users_and_groups)

    def setup(self, old_version):
        """Install and configure the app."""
        super().setup(old_version)
        actions.superuser_run('minidlna', ['setup'])
        if not old_version:
            self.enable()

    def force_upgrade(self, packages):
        """Force upgrade minidlna to resolve conffile prompt."""
        if 'minidlna' not in packages:
            return False

        # Allow upgrade from 1.2.1+dfsg-1+b1 to 1.3.x
        package = packages['minidlna']
        if Version(package['new_version']) > Version('1.4~'):
            return False

        media_dir = get_media_dir()
        install(['minidlna'], force_configuration='new')
        set_media_dir(media_dir)

        return True


def get_media_dir():
    """Return the currently set media directory."""
    return actions.superuser_run('minidlna', ['get-media-dir'])


def set_media_dir(media_dir):
    """Set the media directory from which files will be scanned for sharing."""
    actions.superuser_run('minidlna', ['set-media-dir', '--dir', media_dir])
