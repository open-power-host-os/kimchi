#
# Kimchi
#
# Copyright IBM Corp, 2014
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
from pprint import pformat
from pprint import pprint

from kimchi.model.libvirtconnection import LibvirtConnection
from kimchi.utils import kimchi_log
from kimchi.xmlutils import dictize


def _get_all_host_dev_infos(libvirt_conn):
    node_devs = libvirt_conn.listAllDevices(0)
    return [get_dev_info(node_dev) for node_dev in node_devs]


def _get_dev_info_tree(dev_infos):
    devs = dict([(dev_info['name'], dev_info) for dev_info in dev_infos])
    root = None
    for dev_info in dev_infos:
        if dev_info['parent'] is None:
            root = dev_info
            continue
        parent = devs[dev_info['parent']]

        try:
            children = parent['children']
        except KeyError:
            parent['children'] = [dev_info]
        else:
            children.append(dev_info)
    return root


def _strip_parents(devs, dev):
    parent = dev['parent']
    while parent is not None:
        try:
            parent_dev = devs.pop(parent)
        except KeyError:
            break

        if (parent_dev['device_type'],
                dev['device_type']) == ('usb_device', 'scsi'):
            # For USB device containing mass storage, passthrough the
            # USB device itself, not the SCSI unit.
            devs.pop(dev['name'])
            break

        parent = parent_dev['parent']


def _is_pci_qualified(pci_dev):
    # PCI class such as bridge and storage controller are not suitable to
    # passthrough to VM, so we make a whitelist and only passthrough PCI
    # class in the list.

    whitelist_pci_classes = {
        # Refer to Linux Kernel code include/linux/pci_ids.h
        0x000000: {  # Old PCI devices
            0x000100: None},  # Old VGA devices
        0x020000: None,  # Network controller
        0x030000: None,  # Display controller
        0x040000: None,  # Multimedia device
        0x080000: {  # System Peripheral
            0x088000: None},  # Misc Peripheral, such as SDXC/MMC Controller
        0x090000: None,  # Inupt device
        0x0d0000: None,  # Wireless controller
        0x0f0000: None,  # Satellite communication controller
        0x100000: None,  # Cryption controller
        0x110000: None,  # Signal Processing controller
        }

    with open(os.path.join(pci_dev['path'], 'class')) as f:
        pci_class = int(f.readline().strip(), 16)

    try:
        subclasses = whitelist_pci_classes[pci_class & 0xff0000]
    except KeyError:
        return False

    if subclasses is None:
        return True

    if pci_class & 0xffff00 in subclasses:
        return True

    return False


def get_passthrough_dev_infos(libvirt_conn):
    ''' Get devices eligible to be passed through to VM. '''

    dev_infos = _get_all_host_dev_infos(libvirt_conn)
    devs = dict([(dev_info['name'], dev_info) for dev_info in dev_infos])

    for dev in dev_infos:
        if dev['device_type'] in ('pci', 'usb_device', 'scsi'):
            _strip_parents(devs, dev)

    def is_eligible(dev):
        return dev['device_type'] in ('usb_device', 'scsi') or \
            (dev['device_type'] == 'pci' and _is_pci_qualified(dev))

    return [dev for dev in devs.itervalues() if is_eligible(dev)]


def get_affected_passthrough_devices(libvirt_conn, passthrough_dev):
    devs = dict([(dev['name'], dev) for dev in
                 _get_all_host_dev_infos(libvirt_conn)])

    def get_iommu_group(dev_info):
        try:
            return dev_info['iommuGroup']
        except KeyError:
            pass

        parent = dev_info['parent']
        while parent is not None:
            try:
                iommuGroup = devs[parent]['iommuGroup']
            except KeyError:
                pass
            else:
                return iommuGroup
            parent = devs[parent]['parent']

        return -1

    iommu_group = get_iommu_group(passthrough_dev)

    if iommu_group == -1:
        return []

    return [dev for dev in get_passthrough_dev_infos(libvirt_conn)
            if dev['name'] != passthrough_dev['name'] and
            get_iommu_group(dev) == iommu_group]


def get_dev_info(node_dev):
    ''' Parse the node device XML string into dict according to
    http://libvirt.org/formatnode.html. '''

    xmlstr = node_dev.XMLDesc(0)
    info = dictize(xmlstr)['device']
    dev_type = info['capability'].pop('type')
    info['device_type'] = dev_type
    cap_dict = info.pop('capability')
    info.update(cap_dict)
    info['parent'] = node_dev.parent()

    get_dev_type_info = {
        'net': _get_net_dev_info,
        'pci': _get_pci_dev_info,
        'scsi': _get_scsi_dev_info,
        'scsi_generic': _get_scsi_generic_dev_info,
        'scsi_host': _get_scsi_host_dev_info,
        'scsi_target': _get_scsi_target_dev_info,
        'storage': _get_storage_dev_info,
        'system': _get_system_dev_info,
        'usb': _get_usb_dev_info,
        'usb_device': _get_usb_device_dev_info,
    }
    try:
        get_detail_info = get_dev_type_info[dev_type]
    except KeyError:
        kimchi_log.error("Unknown device type: %s", dev_type)
        return info

    return get_detail_info(info)


def _get_net_dev_info(info):
    cap = info.pop('capability')
    links = {"80203": "IEEE 802.3", "80211": "IEEE 802.11"}
    link_raw = cap['type']
    info['link_type'] = links.get(link_raw, link_raw)

    return info


def _get_pci_dev_info(info):
    for k in ('vendor', 'product'):
        try:
            description = info[k].pop('pyval')
        except KeyError:
            description = None
        info[k]['description'] = description
    if 'path' not in info:
        # Old libvirt does not provide syspath info
        info['path'] = \
            "/sys/bus/pci/devices/" \
            "%(domain)04x:%(bus)02x:%(slot)02x.%(function)01x" % {
                'domain': info['domain'], 'bus': info['bus'],
                'slot': info['slot'], 'function': info['function']}
    try:
        info['iommuGroup'] = int(info['iommuGroup']['number'])
    except KeyError:
        # Old libvirt does not provide syspath info, figure it out ourselves
        iommu_link = os.path.join(info['path'], 'iommu_group')
        if os.path.exists(iommu_link):
            iommu_path = os.path.realpath(iommu_link)
            try:
                info['iommuGroup'] = int(iommu_path.rsplit('/', 1)[1])
            except (ValueError, IndexError):
                # No IOMMU group support at all.
                pass
        else:
            # No IOMMU group support at all.
            pass
    return info


def _get_scsi_dev_info(info):
    return info


def _get_scsi_generic_dev_info(info):
    # scsi_generic is not documented in libvirt official website. Try to
    # parse scsi_generic according to the following libvirt path series.
    # https://www.redhat.com/archives/libvir-list/2013-June/msg00014.html
    return info


def _get_scsi_host_dev_info(info):
    try:
        cap_info = info.pop('capability')
    except KeyError:
        # kimchi.model.libvirtstoragepool.ScsiPoolDef assumes
        # info['adapter']['type'] always exists.
        info['adapter'] = {'type': ''}
        return info
    info['adapter'] = cap_info
    return info


def _get_scsi_target_dev_info(info):
    # scsi_target is not documented in libvirt official website. Try to
    # parse scsi_target according to the libvirt commit db19834a0a.
    return info


def _get_storage_dev_info(info):
    try:
        cap_info = info.pop('capability')
    except KeyError:
        return info

    if cap_info['type'] == 'removable':
        cap_info['available'] = bool(cap_info.pop('media_available'))
        if cap_info['available']:
            for k in ('size', 'label'):
                try:
                    cap_info[k] = cap_info.pop('media_' + k)
                except KeyError:
                    cap_info[k] = None
    info['media'] = cap_info
    return info


def _get_system_dev_info(info):
    return info


def _get_usb_dev_info(info):
    return info


def _get_usb_device_dev_info(info):
    for k in ('vendor', 'product'):
        try:
            info[k]['description'] = info[k].pop('pyval')
        except KeyError:
            # Some USB devices don't provide vendor/product description.
            pass
    return info


# For test and debug
def _print_host_dev_tree(libvirt_conn):
    dev_infos = _get_all_host_dev_infos(libvirt_conn)
    root = _get_dev_info_tree(dev_infos)
    if root is None:
        print "No device found"
        return
    print '-----------------'
    print '\n'.join(_format_dev_node(root))


def _format_dev_node(node):
    try:
        children = node['children']
        del node['children']
    except KeyError:
        children = []

    lines = []
    lines.extend([' ~' + line for line in pformat(node).split('\n')])

    count = len(children)
    for i, child in enumerate(children):
        if count == 1:
            lines.append('   \-----------------')
        else:
            lines.append('   +-----------------')
        clines = _format_dev_node(child)
        if i == count - 1:
            p = '    '
        else:
            p = '   |'
        lines.extend([p + cline for cline in clines])
    lines.append('')

    return lines


if __name__ == '__main__':
    libvirt_conn = LibvirtConnection('qemu:///system').get()
    _print_host_dev_tree(libvirt_conn)
    print 'Eligible passthrough devices:'
    pprint(get_passthrough_dev_infos(libvirt_conn))
