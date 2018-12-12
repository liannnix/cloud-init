# This file is part of cloud-init. See LICENSE file for license information.

import os

from cloudinit import log as logging
from cloudinit.distros.parsers import resolv_conf
from cloudinit import util

from . import renderer


LOG = logging.getLogger(__name__)


class Iface:
    def __init__(self, iface):
        self.iface = iface
        self.match_keys = {
            'name': 'Name',
            'mac_address': 'MACAddress',
        }
        self.network_keys = {
            'gateway': 'Gateway',
            'dns_nameservers': 'DNS',
            'dns_search': 'Domains',
        }

    def render_match_section(self):
        content = '[Match]\n'

        for key in self.match_keys.keys():
            if self.iface.get(key):
                content += '%s=%s\n' % (self.match_keys[key], self.iface[key])

        return content + '\n'

    def render_network_section(self):
        def bad_subnet_type(subnet_type):
            msg = 'Unknown subnet type `%s`' % subnet_type
            LOG.error(msg)
            raise ValueError(msg)

        def render_dhcp(subnet):
            content = ''

            subnet_type = subnet['type']
            if subnet_type in ['dhcp', 'dhcp4']:
                content += 'DHCP=ipv4'
            elif subnet_type == 'dhcp6':
                content += 'DHCP=ipv6'
            else:
                bad_subnet_type(subnet_type)

            return content + '\n'

        def render_static(subnet):
            content = ''

            address = subnet['address']
            subnet_type = subnet['type']
            if subnet_type == 'static':
                ipv4 = True
            elif subnet_type == 'static6':
                ipv4 = False
            else:
                bad_subnet_type(subnet_type)

            content += 'Address=%s\n' % address

            return content + '\n'

        # start of function
        content = '[Network]\n'

        if self.iface.get('subnets'):
            subnet = self.iface['subnets'][0]
            if subnet['type'].startswith('dhcp'):
                content += render_dhcp(subnet)
            elif subnet['type'].startswith('static'):
                content += render_static(subnet)
            else:
                bad_subnet_type(subnet_type)

            for key,values in subnet.items():
                if key in self.network_keys:
                    key = self.network_keys[key]
                    if not isinstance(values, list):
                        values = [values]
                    for value in values:
                        content += '%s=%s\n' % (key, value)
                    if len(values) > 0:
                        content += '\n'

        return content + '\n'

    def render(self):
        content = ''

        content += self.render_match_section()
        content += self.render_network_section()

        return content.rstrip('\n') + '\n'


class Renderer(renderer.Renderer):
    """Renders network information in a /etc/systemd/network format."""

    def __init__(self, config=None):
        if config is None:
            config = {}
        self.networkd_dir = config.get('networkd_dir', 'etc/systemd/network')
        self.dns_path = config.get('dns_path', 'etc/resolv.conf')

    def _render_dns(self, network_state, existing_dns_path=None):
        content = resolv_conf.ResolvConf('')
        if existing_dns_path and os.path.isfile(existing_dns_path):
            content = resolv_conf.ResolvConf(util.load_file(existing_dns_path))
        for nameserver in network_state.dns_nameservers:
            content.add_nameserver(nameserver)
        for searchdomain in network_state.dns_searchdomains:
            content.add_search_domain(searchdomain)
        return str(content)

    def _render_networkd_v2(self, network_state):
        if network_state.version != 2:
            msg = 'Works only with version 2 network configuration'
            LOG.error(msg)
            raise ValueError(msg)

        for interface, data in network_state.config['ethernets'].items():
            content += '[Match]\n'
            if data.get('match'):
                content += 'Name=%s\n' % data['match']

            content += '\n[Network]\n'
            for address in data.get('addresses'):
                content += 'Address=%s\n' % address

    def _render_physical_interface(self, iface):
        content = Iface(iface).render()
        return content

    def _render_networkd(self, networkd_dir, network_state):
        contents = {}

        for iface in network_state.iter_interfaces():
            name = iface['name']
            if iface['type'] == 'loopback':
                continue
            elif iface['type'] == 'physical':
                path = os.path.join(networkd_dir, name + '.network')
                contents[path] = self._render_physical_interface(iface)
            else:
                continue

        return contents

    def render_network_state(self, network_state, templates=None, target=None):
        networkd_dir = util.target_path(target, self.networkd_dir)
        for path, content in self._render_networkd(networkd_dir,
                                                   network_state).items():
            util.write_file(path, content)

        if self.dns_path:
            dns_path = util.target_path(target, self.dns_path)
            resolv_content = self._render_dns(network_state,
                                              existing_dns_path=dns_path)
            util.write_file(dns_path, resolv_content)


def available(target=None):
    expected = ['networkctl']
    search = ['/bin', '/usr/bin']
    for p in expected:
        if not util.which(p, search=search, target=target):
            return False

    expected_dirs = [
        '/etc/systemd/network',
    ]
    for d in expected_dirs:
        if not os.path.isdir(util.target_path(target, d)):
            return False
    return True


# vi: ts=4 expandtab
