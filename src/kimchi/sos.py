### This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.


from sos.plugins import Plugin, RedHatPlugin, UbuntuPlugin, DebianPlugin


class Kimchi(Plugin, RedHatPlugin, UbuntuPlugin, DebianPlugin):
    """kimchi-related information
    """

    plugin_name = 'kimchi'

    def setup(self):
        self.add_copy_specs([
            "/etc/kimchi/",
            "/var/log/kimchi*"
        ])
        self.add_cmd_output("virsh pool-list --details")
        rc, out, _ = self.get_command_output('virsh pool-list')
        if rc == 0:
            for pool in out.splitlines()[2:]:
                if pool:
                    pool_name = pool.split()[0]
                    self.add_cmd_output("virsh vol-list --pool %s --details"
                                        % pool_name)
