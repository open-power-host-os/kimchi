#
# Project Kimchi
#
# Copyright IBM Corp, 2015-2017
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

from wok.control.base import AsyncCollection, Resource
from wok.control.utils import internal_redirect, UrlSubNode

from wok.plugins.kimchi.control.vm import sub_nodes


VMS_REQUESTS = {
    'POST': {
        'default': "KCHVM0001L",
    },
}

VM_REQUESTS = {
    'DELETE': {'default': "KCHVM0002L"},
    'PUT': {'default': "KCHVM0003L"},
    'POST': {
        'start': "KCHVM0004L",
        'poweroff': "KCHVM0005L",
        'shutdown': "KCHVM0006L",
        'reset': "KCHVM0007L",
        'connect': "KCHVM0008L",
        'clone': "KCHVM0009L",
        'migrate': "KCHVM0010L",
        'suspend': "KCHVM0011L",
        'resume': "KCHVM0012L",
        'serial': "KCHVM0013L",
    },
}


@UrlSubNode('vms', True)
class VMs(AsyncCollection):
    def __init__(self, model):
        super(VMs, self).__init__(model)
        self.resource = VM
        self.admin_methods = ['POST']

        # set user log messages and make sure all parameters are present
        self.log_map = VMS_REQUESTS
        self.log_args.update({'name': '', 'template': ''})


class VM(Resource):
    def __init__(self, model, ident):
        super(VM, self).__init__(model, ident)
        self.screenshot = VMScreenShot(model, ident)
        self.virtviewerfile = VMVirtViewerFile(model, ident)
        self.uri_fmt = '/vms/%s'
        for ident, node in sub_nodes.items():
            setattr(self, ident, node(model, self.ident))
        self.start = self.generate_action_handler('start')
        self.poweroff = self.generate_action_handler('poweroff',
                                                     destructive=True)
        self.shutdown = self.generate_action_handler('shutdown',
                                                     destructive=True)
        self.reset = self.generate_action_handler('reset',
                                                  destructive=True)
        self.connect = self.generate_action_handler('connect')
        self.clone = self.generate_action_handler_task('clone')
        self.migrate = self.generate_action_handler_task('migrate',
                                                         ['remote_host',
                                                          'user',
                                                          'password',
                                                          'enable_rdma'])
        self.suspend = self.generate_action_handler('suspend')
        self.resume = self.generate_action_handler('resume')
        self.serial = self.generate_action_handler('serial')

        # set user log messages and make sure all parameters are present
        self.log_map = VM_REQUESTS
        self.log_args.update({'remote_host': ''})

    @property
    def data(self):
        return self.info


class VMScreenShot(Resource):
    def __init__(self, model, ident):
        super(VMScreenShot, self).__init__(model, ident)

    def get(self):
        self.lookup()
        internal_uri = self.info.replace('plugins/kimchi', '')
        raise internal_redirect(internal_uri)


class VMVirtViewerFile(Resource):
    def __init__(self, model, ident):
        super(VMVirtViewerFile, self).__init__(model, ident)

    @property
    def data(self):
        internal_uri = self.info.replace('plugins/kimchi', '')
        raise internal_redirect(internal_uri)
