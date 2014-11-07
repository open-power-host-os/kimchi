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
import time
import urlparse

from ConfigParser import ConfigParser

from kimchi.basemodel import Singleton
from kimchi.config import kimchiLock
from kimchi.exception import InvalidOperation
from kimchi.exception import OperationFailed, NotFoundError, MissingParameter
from kimchi.utils import validate_repo_url


class Repositories(object):
    __metaclass__ = Singleton

    """
    Class to represent and operate with repositories information.
    """
    def __init__(self):
        try:
            __import__('yum')
            self._pkg_mnger = YumRepo()
        except ImportError:
            try:
                __import__('apt_pkg')
                self._pkg_mnger = AptRepo()
            except ImportError:
                raise InvalidOperation('KCHREPOS0014E')

    def addRepository(self, params):
        """
        Add and enable a new repository
        """
        return self._pkg_mnger.addRepo(params)

    def getRepositories(self):
        """
        Return a dictionary with all Kimchi's repositories. Each element uses
        the format {<repo_id>: {repo}}, where repo is a dictionary in the
        repositories.Repositories() format.
        """
        return self._pkg_mnger.getRepositoriesList()

    def getRepository(self, repo_id):
        """
        Return a dictionary with all info from a given repository ID.
        """
        info = self._pkg_mnger.getRepo(repo_id)
        info['repo_id'] = repo_id
        return info

    def enableRepository(self, repo_id):
        """
        Enable a repository.
        """
        return self._pkg_mnger.toggleRepo(repo_id, True)

    def disableRepository(self, repo_id):
        """
        Disable a given repository.
        """
        return self._pkg_mnger.toggleRepo(repo_id, False)

    def updateRepository(self, repo_id, params):
        """
        Update the information of a given repository.
        The input is the repo_id of the repository to be updated and a dict
        with the information to be updated.
        """
        return self._pkg_mnger.updateRepo(repo_id, params)

    def removeRepository(self, repo_id):
        """
        Remove a given repository
        """
        return self._pkg_mnger.removeRepo(repo_id)


class YumRepo(object):
    """
    Class to represent and operate with YUM repositories.
    It's loaded only on those systems listed at YUM_DISTROS and loads necessary
    modules in runtime.
    """
    TYPE = 'yum'
    DEFAULT_CONF_DIR = "/etc/yum.repos.d"

    def __init__(self):
        self._yb = getattr(__import__('yum'), 'YumBase')
        self._conf = getattr(__import__('yum'), 'config')

        self._confdir = self.DEFAULT_CONF_DIR
        reposdir = self._yb().conf.reposdir
        for d in reposdir:
            if os.path.isdir(d):
                self._confdir = d
                break

    def _get_repos(self, errcode):
        try:
            yb = self._yb()
            yb.doLock()
            repos = yb.repos
            yb.doUnlock()
        except Exception, e:
            kimchiLock.release()
            raise OperationFailed(errcode, {'err': str(e)})

        return repos

    def getRepositoriesList(self):
        """
        Return a list of repositories IDs
        """
        kimchiLock.acquire()
        repos = self._get_repos('KCHREPOS0024E')
        kimchiLock.release()
        return repos.repos.keys()

    def getRepo(self, repo_id):
        """
        Return a dictionary in the repositories.Repositories() of the given
        repository ID format with the information of a YumRepository object.
        """
        kimchiLock.acquire()
        repos = self._get_repos('KCHREPOS0025E')
        kimchiLock.release()

        if repo_id not in repos.repos.keys():
            raise NotFoundError("KCHREPOS0012E", {'repo_id': repo_id})

        entry = repos.getRepo(repo_id)

        info = {}
        info['enabled'] = entry.enabled

        baseurl = ''
        if entry.baseurl:
            baseurl = entry.baseurl[0]

        info['baseurl'] = baseurl
        info['config'] = {}
        info['config']['repo_name'] = entry.name
        info['config']['gpgcheck'] = entry.gpgcheck
        info['config']['gpgkey'] = entry.gpgkey
        info['config']['mirrorlist'] = entry.mirrorlist or ''
        return info

    def addRepo(self, params):
        """
        Add a given repository to YumBase
        """
        # At least one base url, or one mirror, must be given.
        baseurl = params.get('baseurl', '')

        config = params.get('config', {})
        mirrorlist = config.get('mirrorlist', '')
        if not baseurl and not mirrorlist:
            raise MissingParameter("KCHREPOS0013E")

        if baseurl:
            validate_repo_url(baseurl)

        if mirrorlist:
            validate_repo_url(mirrorlist)

        repo_id = params.get('repo_id', None)
        if repo_id is None:
            repo_id = "kimchi_repo_%s" % str(int(time.time() * 1000))

        kimchiLock.acquire()
        repos = self._get_repos('KCHREPOS0026E')
        kimchiLock.release()
        if repo_id in repos.repos.keys():
            raise InvalidOperation("KCHREPOS0022E", {'repo_id': repo_id})

        repo_name = config.get('repo_name', repo_id)
        repo = {'baseurl': baseurl, 'mirrorlist': mirrorlist,
                'name': repo_name, 'gpgcheck': 1,
                'gpgkey': [], 'enabled': 1}

        # write a repo file in the system with repo{} information.
        parser = ConfigParser()
        parser.add_section(repo_id)

        for key, value in repo.iteritems():
            if value:
                parser.set(repo_id, key, value)

        repofile = os.path.join(self._confdir, repo_id + '.repo')
        try:
            with open(repofile, 'w') as fd:
                parser.write(fd)
        except:
            raise OperationFailed("KCHREPOS0018E",
                                  {'repo_file': repofile})

        return repo_id

    def toggleRepo(self, repo_id, enable):
        kimchiLock.acquire()
        repos = self._get_repos('KCHREPOS0011E')
        kimchiLock.release()
        if repo_id not in repos.repos.keys():
            raise NotFoundError("KCHREPOS0012E", {'repo_id': repo_id})

        entry = repos.getRepo(repo_id)
        if enable and entry.enabled:
            raise InvalidOperation("KCHREPOS0015E", {'repo_id': repo_id})

        if not enable and not entry.enabled:
            raise InvalidOperation("KCHREPOS0016E", {'repo_id': repo_id})

        kimchiLock.acquire()
        try:
            if enable:
                entry.enable()
            else:
                entry.disable()

            self._conf.writeRawRepoFile(entry)
        except:
            kimchiLock.release()
            if enable:
                raise OperationFailed("KCHREPOS0020E", {'repo_id': repo_id})

            raise OperationFailed("KCHREPOS0021E", {'repo_id': repo_id})
        finally:
            kimchiLock.release()

        return repo_id

    def updateRepo(self, repo_id, params):
        """
        Update a given repository in repositories.Repositories() format
        """
        kimchiLock.acquire()
        repos = self._get_repos('KCHREPOS0011E')
        kimchiLock.release()
        if repo_id not in repos.repos.keys():
            raise NotFoundError("KCHREPOS0012E", {'repo_id': repo_id})

        config = params.get('config', {})
        entry = repos.getRepo(repo_id)

        baseurl = params.get('baseurl', None)
        mirrorlist = config.get('mirrorlist', None)

        if baseurl is not None:
            validate_repo_url(baseurl)
            entry.baseurl = baseurl

        if mirrorlist == '':
            mirrorlist = None

        if mirrorlist is not None:
            validate_repo_url(mirrorlist)
            entry.mirrorlist = mirrorlist

        entry.id = params.get('repo_id', repo_id)
        entry.name = config.get('repo_name', entry.name)
        entry.gpgcheck = config.get('gpgcheck', entry.gpgcheck)
        entry.gpgkey = config.get('gpgkey', entry.gpgkey)
        kimchiLock.acquire()
        self._conf.writeRawRepoFile(entry)
        kimchiLock.release()
        return repo_id

    def removeRepo(self, repo_id):
        """
        Remove a given repository
        """
        kimchiLock.acquire()
        repos = self._get_repos('KCHREPOS0027E')
        kimchiLock.release()
        if repo_id not in repos.repos.keys():
            raise NotFoundError("KCHREPOS0012E", {'repo_id': repo_id})

        entry = repos.getRepo(repo_id)
        parser = ConfigParser()
        with open(entry.repofile) as fd:
            parser.readfp(fd)

        if len(parser.sections()) == 1:
            os.remove(entry.repofile)
            return

        parser.remove_section(repo_id)
        with open(entry.repofile, "w") as fd:
            parser.write(fd)


class AptRepo(object):
    """
    Class to represent and operate with YUM repositories.
    It's loaded only on those systems listed at YUM_DISTROS and loads necessary
    modules in runtime.
    """
    TYPE = 'deb'
    KIMCHI_LIST = "kimchi-source.list"

    def __init__(self):
        getattr(__import__('apt_pkg'), 'init_config')()
        getattr(__import__('apt_pkg'), 'init_system')()
        config = getattr(__import__('apt_pkg'), 'config')
        self.pkg_lock = getattr(__import__('apt_pkg'), 'SystemLock')
        module = __import__('aptsources.sourceslist', globals(), locals(),
                            ['SourcesList'], -1)

        self._sourceparts_path = '/%s%s' % (
            config.get('Dir::Etc'), config.get('Dir::Etc::sourceparts'))
        self._sourceslist = getattr(module, 'SourcesList')
        self.filename = os.path.join(self._sourceparts_path, self.KIMCHI_LIST)
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as fd:
                fd.write("# This file is managed by Kimchi and it must not "
                         "be modified manually\n")

    def _get_repos(self):
        try:
            with self.pkg_lock():
                repos = self._sourceslist()
                repos.refresh()
        except Exception, e:
            kimchiLock.release()
            raise OperationFailed('KCHREPOS0025E', {'err': e.message})

        return repos

    def _get_repo_id(self, repo):
        data = urlparse.urlparse(repo.uri)
        name = data.hostname or data.path
        return '%s-%s-%s' % (name, repo.dist, "-".join(repo.comps))

    def _get_source_entry(self, repo_id):
        kimchiLock.acquire()
        repos = self._get_repos()
        kimchiLock.release()

        for r in repos:
            # Ignore deb-src repositories
            if r.type != 'deb':
                continue

            if self._get_repo_id(r) != repo_id:
                continue

            return r

        return None

    def getRepositoriesList(self):
        """
        Return a list of repositories IDs

        APT repositories there aren't the concept about repository ID, so for
        internal control, the repository ID will be built as described in
        _get_repo_id()
        """
        kimchiLock.acquire()
        repos = self._get_repos()
        kimchiLock.release()

        res = []
        for r in repos:
            # Ignore deb-src repositories
            if r.type != 'deb':
                continue

            res.append(self._get_repo_id(r))

        return res

    def getRepo(self, repo_id):
        """
        Return a dictionary in the repositories.Repositories() format of the
        given repository ID with the information of a SourceEntry object.
        """
        r = self._get_source_entry(repo_id)
        if r is None:
            raise NotFoundError("KCHREPOS0012E", {'repo_id': repo_id})

        info = {'enabled': not r.disabled,
                'baseurl': r.uri,
                'config': {'dist': r.dist,
                           'comps': r.comps}}
        return info

    def addRepo(self, params):
        """
        Add a new APT repository based on <params>
        """
        # To create a APT repository the dist is a required parameter
        # (in addition to baseurl, verified on controller through API.json)
        config = params.get('config', None)
        if config is None:
            raise MissingParameter("KCHREPOS0019E")

        if 'dist' not in config.keys():
            raise MissingParameter("KCHREPOS0019E")

        uri = params['baseurl']
        dist = config['dist']
        comps = config.get('comps', [])

        validate_repo_url(uri)

        kimchiLock.acquire()
        try:
            repos = self._get_repos()
            source_entry = repos.add('deb', uri, dist, comps,
                                     file=self.filename)
            with self.pkg_lock():
                repos.save()
        except Exception as e:
            kimchiLock.release()
            raise OperationFailed("KCHREPOS0026E", {'err': e.message})
        kimchiLock.release()

        return self._get_repo_id(source_entry)

    def toggleRepo(self, repo_id, enable):
        """
        Enable a given repository
        """
        r = self._get_source_entry(repo_id)
        if r is None:
            raise NotFoundError("KCHREPOS0012E", {'repo_id': repo_id})

        if enable and not r.disabled:
            raise InvalidOperation("KCHREPOS0015E", {'repo_id': repo_id})

        if not enable and r.disabled:
            raise InvalidOperation("KCHREPOS0016E", {'repo_id': repo_id})

        if enable:
            line = 'deb'
        else:
            line = '#deb'

        kimchiLock.acquire()
        try:
            repos = self._get_repos()
            with self.pkg_lock():
                repos.remove(r)
                repos.add(line, r.uri, r.dist, r.comps, file=self.filename)
                repos.save()
        except:
            kimchiLock.release()
            if enable:
                raise OperationFailed("KCHREPOS0020E", {'repo_id': repo_id})

            raise OperationFailed("KCHREPOS0021E", {'repo_id': repo_id})
        finally:
            kimchiLock.release()

        return repo_id

    def updateRepo(self, repo_id, params):
        """
        Update a given repository in repositories.Repositories() format
        """
        r = self._get_source_entry(repo_id)
        if r is None:
            raise NotFoundError("KCHREPOS0012E", {'repo_id': repo_id})

        info = {'enabled': not r.disabled,
                'baseurl': params.get('baseurl', r.uri),
                'config': {'type': 'deb', 'dist': r.dist,
                           'comps': r.comps}}

        if 'config' in params.keys():
            config = params['config']
            info['config']['dist'] = config.get('dist', r.dist)
            info['config']['comps'] = config.get('comps', r.comps)

        self.removeRepo(repo_id)
        return self.addRepo(info)

    def removeRepo(self, repo_id):
        """
        Remove a given repository
        """
        r = self._get_source_entry(repo_id)
        if r is None:
            raise NotFoundError("KCHREPOS0012E", {'repo_id': repo_id})

        kimchiLock.acquire()
        try:
            repos = self._get_repos()
            with self.pkg_lock():
                repos.remove(r)
                repos.save()
        except:
            kimchiLock.release()
            raise OperationFailed("KCHREPOS0017E", {'repo_id': repo_id})
        finally:
            kimchiLock.release()
