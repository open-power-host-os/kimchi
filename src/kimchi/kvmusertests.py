# Project Kimchi
#
# Copyright IBM, Corp. 2013
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import platform
import psutil
import uuid


import libvirt


from kimchi.rollbackcontext import RollbackContext


class UserTests(object):
    SIMPLE_VM_XML = """
    <domain type='kvm'>
      <name>%(name)s</name>
      <uuid>%(uuid)s</uuid>
      <memory unit='KiB'>%(memory)s</memory>
      <os>
        <type arch='%(arch)s' machine='%(machine)s'>hvm</type>
        <boot dev='hd'/>
      </os>
    </domain>"""
    user = None

    @classmethod
    def probe_user(cls):
        if cls.user:
            return cls.user

        vm_uuid = uuid.uuid1()
        vm_name = "kimchi_test_%s" % vm_uuid

        if platform.machine().startswith('ppc'):
            arch = "ppc64"
            machine = "pseries"
            memory = "262144"
        else:
            arch = "x86_64"
            machine = "pc"
            memory = "10240"

        xml = cls.SIMPLE_VM_XML % {'name': vm_name, 'uuid': vm_uuid,
                                   'memory': memory, 'arch': arch,
                                   'machine': machine}

        with RollbackContext() as rollback:
            conn = libvirt.open('qemu:///system')
            rollback.prependDefer(conn.close)
            dom = conn.defineXML(xml)
            rollback.prependDefer(dom.undefine)
            dom.create()
            rollback.prependDefer(dom.destroy)
            with open('/var/run/libvirt/qemu/%s.pid' % vm_name) as f:
                pidStr = f.read()
            p = psutil.Process(int(pidStr))

            # bug fix #357
            # in psutil 2.0 and above versions, username will be a method,
            # not a string
            if callable(p.username):
                cls.user = p.username()
            else:
                cls.user = p.username

        return cls.user


if __name__ == '__main__':
    ut = UserTests()
    print ut.probe_user()
