#
# Project Kimchi
#
# Copyright IBM Corp, 2015-2016
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

from wok import template
from wok.control.base import AsyncCollection, Collection, Resource
from wok.control.utils import get_class_name, model_fn


STORAGEVOLUMES_REQUESTS = {
    'POST': {'default': "KCHVOL0001L"},
}

STORAGEVOLUME_REQUESTS = {
    'DELETE': {'default': "KCHVOL0002L"},
    'PUT': {'default': "KCHVOL0003L"},
    'POST': {
        'wipe': "KCHVOL0004L",
        'resize': "KCHVOL0005L",
        'clone': "KCHVOL0006L",
    },
}


class StorageVolumes(AsyncCollection):
    def __init__(self, model, pool):
        super(StorageVolumes, self).__init__(model)
        self.resource = StorageVolume
        self.pool = pool
        self.resource_args = [self.pool, ]
        self.model_args = [self.pool, ]
        self.log_map = STORAGEVOLUMES_REQUESTS
        self.log_args.update({
            'name': '',
            'pool': self.pool.encode('utf-8') if self.pool else '',
        })

    def filter_data(self, resources, fields_filter):
        # filter directory from storage volumes
        fields_filter.update({'type': ['file', 'block', 'network']})
        return super(StorageVolumes, self).filter_data(resources,
                                                       fields_filter)


class StorageVolume(Resource):
    def __init__(self, model, pool, ident):
        super(StorageVolume, self).__init__(model, ident)
        self.pool = pool
        self.ident = ident
        self.info = {}
        self.model_args = [self.pool, self.ident]
        self.uri_fmt = '/storagepools/%s/storagevolumes/%s'
        self.resize = self.generate_action_handler('resize', ['size'])
        self.wipe = self.generate_action_handler('wipe')
        self.clone = self.generate_action_handler_task('clone')

        # set user log messages and make sure all parameters are present
        self.log_map = STORAGEVOLUME_REQUESTS
        self.log_args.update({
            'pool': self.pool.encode('utf-8') if self.pool else '',
            'size': '',
        })

    @property
    def data(self):
        res = {'name': self.ident,
               'type': self.info['type'],
               'capacity': self.info['capacity'],
               'allocation': self.info['allocation'],
               'path': self.info['path'],
               'used_by': self.info['used_by'],
               'format': self.info['format'],
               'isvalid': self.info['isvalid'],
               'has_permission': self.info['has_permission']}

        for key in ('os_version', 'os_distro', 'bootable', 'base'):
            val = self.info.get(key)
            if val:
                res[key] = val

        return res


class IsoVolumes(Collection):
    def __init__(self, model, pool):
        super(IsoVolumes, self).__init__(model)
        self.pool = pool

    def get(self, filter_params):
        res_list = []
        try:
            get_list = getattr(self.model, model_fn(self, 'get_list'))
            res_list = get_list(*self.model_args)
        except AttributeError:
            pass

        return template.render(get_class_name(self), res_list)
