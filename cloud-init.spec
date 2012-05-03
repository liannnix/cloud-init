Name: cloud-init
Version: 0.6.3
Release: alt1
Summary: Cloud instance init scripts

Group: System/Configuration/Boot and Init
License: GPLv3
Url: http://launchpad.net/cloud-init

Source0: %name-%version.tar
Source1: %name-alt.cfg

BuildArch: noarch
BuildRequires: python-devel python-module-distribute

%description
Cloud-init is a set of init scripts for cloud instances.  Cloud instances
need special scripts to run during initialization to retrieve and install
ssh keys and to let the user run various scripts.

%prep
%setup

%build
%python_build

%install
%python_install

for x in $RPM_BUILD_ROOT/%_bindir/*.py; do mv "$x" "${x%%.py}"; done
chmod +x $RPM_BUILD_ROOT/%python_sitelibdir/cloudinit/SshUtil.py
mkdir -p $RPM_BUILD_ROOT/%_sharedstatedir/cloud

# We supply our own config file since our software differs from Ubuntu's.
cp -p %SOURCE1 $RPM_BUILD_ROOT/%_sysconfdir/cloud/cloud.cfg

%files
%doc ChangeLog LICENSE TODO
%config(noreplace) %_sysconfdir/cloud/cloud.cfg
%dir               %_sysconfdir/cloud/cloud.cfg.d
%config(noreplace) %_sysconfdir/cloud/cloud.cfg.d/*.cfg
%doc               %_sysconfdir/cloud/cloud.cfg.d/README
%dir               %_sysconfdir/cloud/templates
%config(noreplace) %_sysconfdir/cloud/templates/*
%systemd_unitdir/cloud-config.service
%systemd_unitdir/cloud-config.target
%systemd_unitdir/cloud-final.service
%systemd_unitdir/cloud-init-local.service
%systemd_unitdir/cloud-init.service
%python_sitelibdir/*
%_libexecdir/%name
%_bindir/cloud-init*
%doc %_datadir/doc/%name
%dir %_sharedstatedir/cloud

%config(noreplace) %_sysconfdir/rsyslog.d/21-cloudinit.conf

%changelog
* Thu May 03 2012 Vitaly Kuznetsov <vitty@altlinux.ru> 0.6.3-alt1
- initial

