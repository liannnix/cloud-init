# vi: ts=4 expandtab
#
#    Copyright (C) 2016 Canonical Ltd.
#
#    Author: Ryan Harper <ryan.harper@canonical.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License version 3, as
#    published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from cloudinit import log as logging
from cloudinit.settings import PER_INSTANCE
from cloudinit import templater
from cloudinit import type_utils
from cloudinit import util

import os

LOG = logging.getLogger(__name__)

frequency = PER_INSTANCE
NTP_CONF = '/etc/ntp.conf'
NR_POOL_SERVERS = 4
distros = ['centos', 'debian', 'fedora', 'opensuse', 'ubuntu', 'altlinux']


def handle(name, cfg, cloud, log, _args):
    """
    Enable and configure ntp

    ntp:
       pools: ['0.{{distro}}.pool.ntp.org', '1.{{distro}}.pool.ntp.org']
       servers: ['192.168.2.1']

    """

    ntp_cfg = cfg.get('ntp', {})

    if not isinstance(ntp_cfg, (dict)):
        raise RuntimeError(("'ntp' key existed in config,"
                            " but not a dictionary type,"
                            " is a %s %instead"), type_utils.obj_name(ntp_cfg))

    if 'ntp' not in cfg:
        LOG.debug("Skipping module named %s,"
                  "not present or disabled by cfg", name)
        return True

    install_ntp(cloud.distro.install_packages, packages=['ntp'],
                check_exe="ntpd")
    rename_ntp_conf()
    write_ntp_config_template(ntp_cfg, cloud)


def install_ntp(install_func, packages=None, check_exe="ntpd"):
    if util.which(check_exe):
        return
    if packages is None:
        packages = ['ntp']

    install_func(packages)


def rename_ntp_conf(config=NTP_CONF):
    if os.path.exists(config):
        util.rename(config, config + ".dist")


def generate_server_names(distro):
    names = []
    for x in range(0, NR_POOL_SERVERS):
        name = "%d.%s.pool.ntp.org" % (x, distro)
        names.append(name)
    return names


def write_ntp_config_template(cfg, cloud):
    servers = cfg.get('servers', [])
    pools = cfg.get('pools', [])

    if len(servers) == 0 and len(pools) == 0:
        LOG.debug('Adding distro default ntp pool servers')
        pools = generate_server_names(cloud.distro.name)

    params = {
        'servers': servers,
        'pools': pools,
    }

    template_fn = cloud.get_template_filename('ntp.conf.%s' %
                                              (cloud.distro.name))
    if not template_fn:
        template_fn = cloud.get_template_filename('ntp.conf')
        if not template_fn:
            raise RuntimeError(("No template found, "
                                "not rendering %s"), NTP_CONF)

    templater.render_to_file(template_fn, NTP_CONF, params)
