%define mcp 8
%if 0%{?fedora} >= 15 || 0%{?rhel} >= 7 || 0%{?mcp} >= 8
%global with_systemd 1
%endif

%define frobisher_release 20
%define release .9
Name:		kimchi
Version:	1.2.1
Release:	%{?frobisher_release}%{?release}%{?dist}
Summary:	Kimchi server application
BuildRoot:	%{_topdir}/BUILD/%{name}-%{version}-%{release}
Group:		System Environment/Base
License:	LGPL/ASL2
Requires:	qemu-kvm
Requires:	libvirt
Requires:	libvirt-python
Requires:	python-cherrypy >= 3.2.0
Requires:	python-cheetah
Requires:	m2crypto
Requires:	python-imaging
Requires:	libxml2-python
Requires:	PyPAM
Requires:	pyparted
Requires:	python-psutil >= 0.6.0
Requires:	python-jsonschema >= 1.3.0
Requires:	python-ethtool
Requires:	sos
Requires:	python-ipaddr
Requires:	python-lxml
Requires:	nfs-utils
Requires:	nginx
Requires:	iscsi-initiator-utils
Requires:	policycoreutils
Requires:	policycoreutils-devel
Requires:	policycoreutils-python

Requires(post): policycoreutils
Requires(post): policycoreutils-python
Requires(post): selinux-policy-targeted
Requires(postun): policycoreutils
Requires(postun): policycoreutils-python
Requires(postun): selinux-policy-targeted

%if 0%{?rhel} == 6
Requires:	python-ordereddict
Requires:	python-imaging
BuildRequires:    python-unittest2
%endif

%if 0%{?with_systemd}
Requires:	systemd
Requires:	firewalld
Requires(post): systemd
Requires(post): firewalld
Requires(preun): systemd
Requires(preun): firewalld
Requires(postun): systemd
%endif

%if 0%{?with_systemd}
BuildRequires: systemd-units
%endif

BuildRequires:	git
BuildRequires:	autoconf
BuildRequires:	automake
BuildRequires:	gettext-devel
BuildRequires:  libxslt
BuildRequires:  libxml2-python
BuildRequires:  selinux-policy-devel

%description
Web server application to manage KVM/Qemu virtual machines

%prep
git clone git@git.linux.ibm.com:kimchi-ginger/kimchi.git ./
git checkout --track remotes/origin/pkvm-2.1.1

%build
./autogen.sh --system
make
cd selinux
make -f /usr/share/selinux/devel/Makefile


%install
rm -rf %{buildroot}
make DESTDIR=%{buildroot} install
install -Dm 0644 src/kimchi/sos.py \
                 %{buildroot}/%{python_sitelib}/sos/plugins/kimchi.py

%if 0%{?with_systemd}
# Install the systemd scripts
install -Dm 0644 contrib/kimchid.service.fedora %{buildroot}%{_unitdir}/kimchid.service
install -Dm 0640 src/firewalld.xml %{buildroot}%{_sysconfdir}/firewalld/services/kimchid.xml
install -Dm 0744 src/kimchi-firewalld.sh %{buildroot}%{_datadir}/kimchi/utils/kimchi-firewalld.sh
install -Dm 0744 selinux/kimchid.pp %{buildroot}%{_datadir}/kimchi/selinux/kimchid.pp
%endif

%if 0%{?rhel} == 6
# Install the upstart script
install -Dm 0755 contrib/kimchid-upstart.conf.fedora %{buildroot}/etc/init/kimchid.conf
%endif
%if 0%{?rhel} == 5
# Install the SysV init scripts
install -Dm 0755 contrib/kimchid.sysvinit %{buildroot}%{_initrddir}/kimchid
%endif

%post
if [ $1 -eq 1 ] ; then
    /bin/systemctl enable kimchid.service >/dev/null 2>&1 || :
    # Initial installation
    /bin/systemctl daemon-reload >/dev/null 2>&1 || :
fi

sed -i s/#host/host/ /etc/kimchi/kimchi.conf
service firewalld status >/dev/null 2>&1
if [ $? -ne 0 ]; then
    service firewalld start >/dev/null 2>&1
fi
if [ $1 -eq 1 ]; then
    # Add kimchid as default service into public chain of firewalld
    %{_datadir}/kimchi/utils/kimchi-firewalld.sh public add kimchid
    firewall-cmd --reload > /dev/null 2>&1 || :
fi
# Install SELinux policy
semodule -i %{_datadir}/kimchi/selinux/kimchid.pp


%preun
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /bin/systemctl --no-reload disable kimchid.service > /dev/null 2>&1 || :
    /bin/systemctl stop kimchid.service > /dev/null 2>&1 || :
    %{_datadir}/kimchi/utils/kimchi-firewalld.sh public del kimchid
    firewall-cmd --reload >/dev/null 2>&1 || :
fi
exit 0


%postun
if [ "$1" -ge 1 ] ; then
    /bin/systemctl try-restart kimchid.service >/dev/null 2>&1 || :
fi
if [ $1 -eq 0 ] ; then
    # Remove the SELinux policy, only during uninstall of the package
    semodule -r kimchid
fi
exit 0
%clean
rm -rf $RPM_BUILD_ROOT

%files
%attr(-,root,root)
%{_bindir}/kimchid
%{python_sitelib}/kimchi/*.py*
%{python_sitelib}/kimchi/control/*.py*
%{python_sitelib}/kimchi/control/vm/*.py*
%{python_sitelib}/kimchi/model/*.py*
%{python_sitelib}/kimchi/API.json
%{python_sitelib}/kimchi/plugins/*.py*
%{python_sitelib}/sos/plugins/kimchi.py*
%{_datadir}/kimchi/doc/API.md
%{_datadir}/kimchi/doc/README.md
%{_datadir}/kimchi/doc/kimchi-guest.png
%{_datadir}/kimchi/doc/kimchi-templates.png
%{_datadir}/kimchi/mo/*/LC_MESSAGES/kimchi.mo
%{_datadir}/kimchi/config/ui/*.xml
%{_datadir}/kimchi/ui/css/fonts/fontawesome-webfont.*
%{_datadir}/kimchi/ui/css/fonts/novnc/Orbitron700.*
%{_datadir}/kimchi/ui/css/novnc/base.css
%{_datadir}/kimchi/ui/css/theme-default.min.css
%{_datadir}/kimchi/ui/images/*.png
%{_datadir}/kimchi/ui/images/*.ico
%{_datadir}/kimchi/ui/images/theme-default/*.png
%{_datadir}/kimchi/ui/images/theme-default/*.gif
%{_datadir}/kimchi/ui/js/kimchi.min.js
%{_datadir}/kimchi/ui/js/jquery-ui.js
%{_datadir}/kimchi/ui/js/jquery.min.js
%{_datadir}/kimchi/ui/js/modernizr.custom.2.6.2.min.js
%{_datadir}/kimchi/ui/js/novnc/*.js
%{_datadir}/kimchi/ui/js/spice/*.js
%{_datadir}/kimchi/ui/js/novnc/web-socket-js/WebSocketMain.swf
%{_datadir}/kimchi/ui/js/novnc/web-socket-js/swfobject.js
%{_datadir}/kimchi/ui/js/novnc/web-socket-js/web_socket.js
%{_datadir}/kimchi/ui/libs/jquery-ui-i18n.min.js
%{_datadir}/kimchi/ui/libs/jquery-ui.min.js
%{_datadir}/kimchi/ui/libs/jquery-1.10.0.min.js
%{_datadir}/kimchi/ui/libs/modernizr.custom.76777.js
%{_datadir}/kimchi/ui/libs/themes/base/images/*.png
%{_datadir}/kimchi/ui/libs/themes/base/images/*.gif
%{_datadir}/kimchi/ui/libs/themes/base/jquery-ui.min.css
%{_datadir}/kimchi/ui/pages/*.tmpl
%{_datadir}/kimchi/ui/pages/help/*/*.html
%{_datadir}/kimchi/ui/pages/help/kimchi.css
%{_datadir}/kimchi/ui/pages/tabs/*.html.tmpl
%{_datadir}/kimchi/ui/pages/websockify/*.html
%{_sysconfdir}/kimchi/kimchi.conf
%{_sysconfdir}/kimchi/nginx.conf.in
%{_sysconfdir}/kimchi/distros.d/debian.json
%{_sysconfdir}/kimchi/distros.d/fedora.json
%{_sysconfdir}/kimchi/distros.d/opensuse.json
%{_sysconfdir}/kimchi/distros.d/ubuntu.json
%{_sysconfdir}/kimchi/distros.d/gentoo.json

%if 0%{?with_systemd}
%{_unitdir}/kimchid.service
%{_datadir}/kimchi/utils/kimchi-firewalld.sh
%{_datadir}/kimchi/selinux/kimchid.pp
%{_sysconfdir}/firewalld/services/kimchid.xml
%endif
%if 0%{?rhel} == 6
/etc/init/kimchid.conf
%endif
%if 0%{?rhel} == 5
%{_initrddir}/kimchid
%endif

%changelog
* Thu Aug 22 2014 Rodrigo Trujillo <rodrigo.trujillo@linux.vnet.ibm.com> 1.2.1-20.9
- Update spec file to PowerKVM 2.1.1 (build 9) 
- Refactor vmstorage name generation - BZ #114093, BZ #113768
- Update testcases for bus type decision making - BZ #114093, BZ #113768
- Delete 'bus' selection from UI - BZ #114093, BZ #113768
- Delete 'bus' param from backend - BZ #114093, BZ #113768
- Bugfix UI: Change button text to indicate user network is generating - BZ #113748
- Bugfix: Log out from Administrator tab raises popup errors - BZ #114203

* Thu Aug 15 2014 Rodrigo Trujillo <rodrigo.trujillo@linux.vnet.ibm.com> 1.2.1-20.8
- Update spec file to PowerKVM 2.1.1 (build 8)
- Increasing nginx proxy timeout - Bugzilla #114166
- Change default environment configuration to production mode - Bugzilla #114301
- update po files - Bugzilla #114427
- Passthrough: Add PCI Devices to VM - Bugzilla #114427
- Host device passthrough: Add unit tests and documents - Bugzilla #114426
- Host device passthrough: List VMs that are holding a host device - Bugzilla #114426
- Host device passthrough: Directly assign and dissmis host device from VM - Bugzilla #114426
- Host device passthrough: List eligible device to passthrough - Bugzilla #114426
- Host device passthrough: List all types of host devices - Bugzilla #114426
- Fix UI: Show proper message when detaching a guest storage - Bugzilla #113754
- Add unit tests for remote-backed CD ROM updates. - Bugzilla #114461
- Fix verification of remote ISO - Bugzilla #114461
- Fix Key Error when editing CD ROM path - Bugzilla #114461
- Remote ISO attachment: fix UI to accept remote ISO link for cdrom attachment - Bugzilla #113761

* Thu Aug 07 2014 Rodrigo Trujillo <rodrigo.trujillo@linux.vnet.ibm.com> 1.2.1-20.7
- Update spec file to PowerKVM 2.1.1 (build 7)
- Let frontend redirect user after logging - Bugzila #114339
- Remove special console rules from nginx configuration - Bugzila #114339
- Remove former login design files - Bugzila #114339
- Update test case to reflect new login design - Bugzila #114339

* Thu Jul 31 2014 Rodrigo Trujillo <rodrigo.trujillo@linux.vnet.ibm.com> 1.2.1-20.6
- Update spec file to PowerKVM 2.1.1 (build 6)
- Disable vhost feature in Ubuntu and SLES (PPC64 LE) - Bugzilla #113883
- Change modern distro versions for PPC - Bugzilla #113883
- Add SUSE's products - Bugzilla #113883
- fix test case for volume filtering - Bugzilla #113755
- Filter directory in storage volume listing - Bugzilla #113755

* Mon Jul 14 2014 Paulo Vital  <pvital@linux.vnet.ibm.com> 1.2.1-20.3
- Update spec file to PowerKVM 2.1.1 (20.3)

* Thu Jul 10 2014 Paulo Vital  <pvital@linux.vnet.ibm.com> 1.2.0-12.2
- Update spec file to PowerKVM 2.1-SP2 (19.2)

* Mon Jun 23 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-19.1
- Guest disks: Update doc to support manage guest disks - Bugzilla #109256
- Guest disks: Update api definition and error reporting - Bugzilla #109256
- Guest disks: Choose proper bus for device - Bugzilla #109256
- Guest disks: Abstract vm disk functions - Bugzilla #109256
- Guest disk: deals with disk attachment - Bugzilla #109256
- Multiple pep8 fixes - Bugzilla #109256
- Guest disks: Update testcase - Bugzilla #109256
- Fix select menu data append - Bugzilla #109256
- UI: Support add guest disk - Bugzilla #109256
- Display all disk types in storage edit view - Bugzilla #109256
- Adjust Guest Edit Storage Tab Styles - Bugzilla #109256
- Change doc and controllor to support cdrom eject - Bugzilla #109256
- Update model to support cdrom eject - Bugzilla #109256
- Add testcase for cdrom eject - Bugzilla #109256
- Bugfix: List inactive network interface while editing template - Bugzilla #108811
- Create pool UI: making 'Create' button disable when forms not filled. - Bugzilla #103725
- Host info: Add support to Power. - Bugzilla #111766
- bug fix: network name can be any characters except " and / - Bugzilla #110626
- Update spec file to PowerKVM 2.1-SP2 (19.1)

* Tue Jun 17 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-18.1
- Fix error storage pool lookup usage in deep scan - Bugzilla #109256
- Remove cdrom '.iso' suffix checking from add template js - Bugzilla #109048
- Remove '.iso' extension checking from json schema - Bugzilla #109048
- Add Ubuntu as modern distro to Power guests - Bugzilla #111243
- Add PowerKVM information as ISO otpion to installation
- Add FW commit and reject capability. - Bugzilla #110827
- Enhancing Power Management error messages - Bugzilla #111099
- Update spec file to get code from LTC Git server
- Update spec file to PowerKVM 2.1-SP1.1

* Fri May 30 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-17.3
- Add selinux-policy-targeted as post requirement - Bugzilla #110928

* Thu May 29 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-16.2
- SELinux policy to allow nginx and kimchid - Bugzilla #110928

* Mon May 12 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-16.1
- Added support to sosreport plugin files - Bugzilla #109913

* Mon May 09 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-16.0
- Updated spec file to build16

* Mon May 05 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-15.2
- Updated spec file to build15.2/beta7.2

* Mon May 05 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-15.2
- Updated spec file to build15.2/beta7.2

* Tue Apr 29 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-15.1
- Updated spec file to build15.1/beta7.1
- Added policycoreutils-devel as policy

* Thu Apr 17 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-14.1
- Added support to no root execution - Bugzilla #104785
- Added support to Kimchi version (upstream)

* Mon Apr 14 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-14.0
- Updated spec file to build14/beta6

* Mon Mar 28 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.2.0-13.0
- Updated Kimchi version to 1.2.0
- Updated spec file to buil13/beta5
- Updated spec to requires firewalld in %post and %preun
- Changed path of kimchi-firewalld.sh from /usr/libexec/kimchi/ to %{_datadir}/kimchi/utils/

* Mon Mar 17 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.1.0-12.0
- Updated spec file to buil12/beta4

* Fri Mar 07 2014 Paulo Vital <pvital@linux.vnet.ibm.com> 1.1.0-11.2
- Updated to divide Kimchi and Kimchi-ginger files in different packages.

* Tue Feb 04 2014 Crístian Viana <vianac@linux.vnet.ibm.com> 1.1.0-10.0
- Bug 103323 - kimchi: IP Validation for nfs pool
- Bug 103324 - kimch hangs: When NFS pool is failed to activate
- Rebase to Kimchi commit f84b4d5
- Commit: Ginger plugin structure files
- Commit: PowerManagement backend: controller, model and API changes
- Commit: PowerManagement backend: changes in common ginger files
- Commit: Ginger users basic management back-end
- Commit: Fix systemd service dependencies of ginger
- Commit: Host basic information: fix blank output to Processor info in ppc
- Commit: Host basic information: fix blank output to OS in Frobisher
- Commit: bug fix: Set full path to guest page file in guest tab
- Commit: Packaging: sync spec file with community's spec
- Commit: Bump SPEC file to pbeta1

* Wed Jan 22 2014 Li Yong Qiao <qiaoly@cn.ibm.com> 1.1.0-8.0
- Isoinfo: Fix return of not bootable PPC ISOs
- vmtemplates: fix PPC templates
- Bug 99069 - Kimchi:Remote ISO image option for add new template inactive
- Bug 99630 - kimchi support for RHEL 7 guest
- Bug 99974 - Kvmonpower_build0.4:Kimchi: Opening from browser failed if firewall is on
- Bug 100671 - Kvmonpower_build0.5:Kimchi: libvirt Domain Config internal error No guest options available for arch 'x86_64'
- Bug 100861 - Host basic information not displayed when using Forbisher
- Bug 102507 - Kvmonpower_build0.6:Kimchi:Deep scan for ISOs not displaying all the available ISOs

* Mon Jan 20 2014 Paulo Vital <pvital@br.ibm.com> 1.1.0-7.1
- Updated spec file to add new runtime requirements and files to be installed.

* Thu Jan 9 2014 Paulo Vital <pvital@br.ibm.com> 1.1.0-7.1
- LTC bug #99974: removing deprecated iptables rules and adding firewalld commands

* Thu Jan 7 2014 Li Yong Qiao <qiaoly@cn.ibm.com> 1.1.0-7.0
- Frobisher pbuild7, bump to 1.1.0
- Fix LTC bug #100861 Host basic information:fix blank output to OS in Frobisher,
- Frobisher will provide the file /etc/ibm_powerkvm-release with OS informantion.

* Thu Dec 12 2013 Li Yong Qiao <qiaoly@cn.ibm.com> 1.0.1-6.1
- Frobisher pbuild6 update 1
- LTC Bugzilla : #100861 : fix blank output to Processor info in ppc
- Fix ppc scan : After the addtion of remote iso scan, the assignature of scan methods changed. 

* Mon Dec 9 2013 Li Yong Qiao <qiaoly@cn.ibm.com> 1.0.1-6.0
- Frobisher pbuild6

* Wed Nov 20 2013 Li Yong Qiao <qiaoly@cn.ibm.com> 1.0.1-2
- Frobisher pbuild5

* Thu Oct 10 2013 Li Yong Qiao <qiaoly@cn.ibm.com> 1.0.1-1
- Adapted for koji build on mcp koji server

* Tue Jul 16 2013 Adam Litke <agl@us.ibm.com> 0.1.0-1
- Adapted for autotools build

* Thu Apr 04 2013 Aline Manera <alinefm@br.ibm.com> 0.0-1
- First build
