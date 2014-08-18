#
# Project Kimchi
#
# Copyright IBM, Corp. 2014
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA

import os
import re
import socket
import string
import urlparse

import lxml.etree as ET
from lxml import etree
from lxml.builder import E

from kimchi.exception import InvalidOperation, InvalidParameter, NotFoundError
from kimchi.exception import OperationFailed
from kimchi.model.vms import DOM_STATE_MAP, VMModel
from kimchi.model.storagevolumes import StorageVolumeModel
from kimchi.model.utils import get_vm_config_flag
from kimchi.utils import check_url_path
from kimchi.osinfo import lookup
from kimchi.vmdisks import get_device_xml, get_vm_disk, get_vm_disk_list
from kimchi.vmdisks import DEV_TYPE_SRC_ATTR_MAP

HOTPLUG_TYPE = ['scsi', 'virtio']


def _get_device_bus(dev_type, dom):
    try:
        version, distro = VMModel.vm_get_os_metadata(dom)
    except:
        version, distro = ('unknown', 'unknown')
    return lookup(distro, version)[dev_type+'_bus']


def _get_storage_xml(params, ignore_source=False):
    src_type = params.get('src_type')
    disk = E.disk(type=src_type, device=params.get('type'))
    disk.append(E.driver(name='qemu', type=params['format']))

    disk.append(E.target(dev=params.get('dev'), bus=params['bus']))
    if params.get('address'):
        # ide disk target id is always '0'
        disk.append(E.address(
            type='drive', controller=params['address']['controller'],
            bus=params['address']['bus'], target='0',
            unit=params['address']['unit']))

    if ignore_source:
        return ET.tostring(disk)

    # Working with url paths
    if src_type == 'network':
        output = urlparse.urlparse(params.get('path'))
        port = str(output.port or socket.getservbyname(output.scheme))
        host = E.host(name=output.hostname, port=port)
        source = E.source(protocol=output.scheme, name=output.path)
        source.append(host)
        disk.append(source)
    else:
        # Fixing source attribute
        source = E.source()
        source.set(DEV_TYPE_SRC_ATTR_MAP[src_type], params.get('path'))
        disk.append(source)

    return ET.tostring(disk)


def _check_path(path):
    if check_url_path(path):
        src_type = 'network'
    # Check if path is a valid local path
    elif os.path.exists(path):
        if os.path.isfile(path):
            src_type = 'file'
        else:
            # Check if path is a valid cdrom drive
            with open('/proc/sys/dev/cdrom/info') as cdinfo:
                content = cdinfo.read()

            cds = re.findall("drive name:\t\t(.*)", content)
            if not cds:
                raise InvalidParameter("KCHVMSTOR0003E", {'value': path})

            drives = [os.path.join('/dev', p) for p in cds[0].split('\t')]
            if path not in drives:
                raise InvalidParameter("KCHVMSTOR0003E", {'value': path})

            src_type = 'block'
    else:
        raise InvalidParameter("KCHVMSTOR0003E", {'value': path})
    return src_type


class VMStoragesModel(object):
    def __init__(self, **kargs):
        self.conn = kargs['conn']
        self.objstore = kargs['objstore']

    def _get_available_bus_address(self, bus_type, vm_name):
        if bus_type not in ['ide']:
            return dict()
        # libvirt limitation of just 1 ide controller
        # each controller have at most 2 buses and each bus 2 units.
        dom = VMModel.get_vm(vm_name, self.conn)
        disks = self.get_list(vm_name)
        valid_id = [('0', '0'), ('0', '1'), ('1', '0'), ('1', '1')]
        controller_id = '0'
        for dev_name in disks:
            disk = get_device_xml(dom, dev_name)
            if disk.target.attrib['bus'] == 'ide':
                controller_id = disk.address.attrib['controller']
                bus_id = disk.address.attrib['bus']
                unit_id = disk.address.attrib['unit']
                if (bus_id, unit_id) in valid_id:
                    valid_id.remove((bus_id, unit_id))
                    continue
        if not valid_id:
            raise OperationFailed('KCHVMSTOR0014E',
                                  {'type': 'ide', 'limit': 4})
        else:
            address = {'controller': controller_id,
                       'bus': valid_id[0][0], 'unit': valid_id[0][1]}
            return dict(address=address)

    def create(self, vm_name, params):
        dom = VMModel.get_vm(vm_name, self.conn)
        # Use device name passed or pick next
        dev_name = params.get('dev', None)
        if dev_name is None:
            params['dev'] = self._get_storage_device_name(vm_name)
        else:
            devices = self.get_list(vm_name)
            if dev_name in devices:
                raise OperationFailed(
                    'KCHVMSTOR0004E',
                    {'dev_name': dev_name, 'vm_name': vm_name})

        # Path will never be blank due to API.json verification.
        # There is no need to cover this case here.
        params['format'] = 'raw'
        if not ('vol' in params) ^ ('path' in params):
            raise InvalidParameter("KCHVMSTOR0017E")
        if params.get('vol'):
            try:
                pool = params['pool']
                vol_info = StorageVolumeModel(
                    conn=self.conn,
                    objstore=self.objstore).lookup(pool, params['vol'])
            except KeyError:
                raise InvalidParameter("KCHVMSTOR0012E")
            except Exception as e:
                raise InvalidParameter("KCHVMSTOR0015E", {'error': e})
            if vol_info['ref_cnt'] != 0:
                raise InvalidParameter("KCHVMSTOR0016E")
            params['format'] = vol_info['format']
            params['path'] = vol_info['path']
        params['src_type'] = _check_path(params['path'])
        params['bus'] = _get_device_bus(params['type'], dom)
        if (params['bus'] not in HOTPLUG_TYPE
                and DOM_STATE_MAP[dom.info()[0]] != 'shutoff'):
            raise InvalidOperation('KCHVMSTOR0011E')

        params.update(self._get_available_bus_address(params['bus'], vm_name))
        # Add device to VM
        dev_xml = _get_storage_xml(params)
        try:
            conn = self.conn.get()
            dom = conn.lookupByName(vm_name)
            dom.attachDeviceFlags(dev_xml, get_vm_config_flag(dom, 'all'))
        except Exception as e:
            raise OperationFailed("KCHVMSTOR0008E", {'error': e.message})
        return params['dev']

    def _get_storage_device_name(self, vm_name):
        dev_list = [dev for dev in self.get_list(vm_name)
                    if dev.startswith('hd')]
        if len(dev_list) == 0:
            return 'hda'
        dev_list.sort()
        last_dev = dev_list.pop()
        # TODO: Improve to device names "greater then" hdz
        next_dev_letter_pos = string.ascii_lowercase.index(last_dev[2]) + 1
        return 'hd' + string.ascii_lowercase[next_dev_letter_pos]

    def get_list(self, vm_name):
        dom = VMModel.get_vm(vm_name, self.conn)
        return get_vm_disk_list(dom)


class VMStorageModel(object):
    def __init__(self, **kargs):
        self.conn = kargs['conn']

    def lookup(self, vm_name, dev_name):
        # Retrieve disk xml and format return dict
        dom = VMModel.get_vm(vm_name, self.conn)
        return get_vm_disk(dom, dev_name)

    def delete(self, vm_name, dev_name):
        # Get storage device xml
        dom = VMModel.get_vm(vm_name, self.conn)
        try:
            bus_type = self.lookup(vm_name, dev_name)['bus']
        except NotFoundError:
            raise

        dom = VMModel.get_vm(vm_name, self.conn)
        if (bus_type not in HOTPLUG_TYPE and
                DOM_STATE_MAP[dom.info()[0]] != 'shutoff'):
            raise InvalidOperation('KCHVMSTOR0011E')

        try:
            conn = self.conn.get()
            dom = conn.lookupByName(vm_name)
            disk = get_device_xml(dom, dev_name)
            dom.detachDeviceFlags(etree.tostring(disk),
                                  get_vm_config_flag(dom, 'all'))
        except Exception as e:
            raise OperationFailed("KCHVMSTOR0010E", {'error': e.message})

    def update(self, vm_name, dev_name, params):
        if params.get('path'):
            params['src_type'] = _check_path(params['path'])
            ignore_source = False
        else:
            params['src_type'] = 'file'
            ignore_source = True
        dom = VMModel.get_vm(vm_name, self.conn)

        dev_info = self.lookup(vm_name, dev_name)
        if dev_info['type'] != 'cdrom':
            raise InvalidOperation("KCHVMSTOR0006E")
        dev_info.update(params)
        xml = _get_storage_xml(dev_info, ignore_source)

        try:
            dom.updateDeviceFlags(xml, get_vm_config_flag(dom, 'all'))
        except Exception as e:
            raise OperationFailed("KCHVMSTOR0009E", {'error': e.message})
        return dev_name

    def eject(self, vm_name, dev_name):
        return self.update(vm_name, dev_name, dict())
