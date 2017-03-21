# This file is part of cloud-init. See LICENSE file for license information.

import os
import re

import six

from cloudinit.distros.parsers import resolv_conf
from cloudinit import util

from . import renderer


def _make_header(sep='#'):
    lines = [
        "Created by cloud-init on instance boot automatically, do not edit.",
        "",
    ]
    for i in range(0, len(lines)):
        if lines[i]:
            lines[i] = sep + " " + lines[i]
        else:
            lines[i] = sep
    return "\n".join(lines)


def _is_default_route(route):
    if route['network'] == '::' and route['netmask'] == 0:
        return True
    if route['network'] == '0.0.0.0' and route['netmask'] == '0.0.0.0':
        return True
    return False


def _quote_value(value):
    if re.search(r"\s", value):
        # This doesn't handle complex cases...
        if value.startswith('"') and value.endswith('"'):
            return value
        else:
            return '"%s"' % value
    else:
        return value


class ConfigMap(object):
    """Sysconfig like dictionary object."""

    # Why does redhat prefer yes/no to true/false??
    _bool_map = {
        True: 'yes',
        False: 'no',
    }

    def __init__(self):
        self._conf = {}

    def __setitem__(self, key, value):
        self._conf[key] = value

    def drop(self, key):
        self._conf.pop(key, None)

    def __len__(self):
        return len(self._conf)

    def to_string(self):
        buf = six.StringIO()
        buf.write(_make_header())
        if self._conf:
            buf.write("\n")
        for key in sorted(self._conf.keys()):
            value = self._conf[key]
            if isinstance(value, bool):
                value = self._bool_map[value]
            if not isinstance(value, six.string_types):
                value = str(value)
            buf.write("%s=%s\n" % (key, _quote_value(value)))
        return buf.getvalue()


class Route(ConfigMap):
    """Represents a route configuration."""

    route4_fn_tpl = '%(base)s/%(name)s/ipv4route'
    route6_fn_tpl = '%(base)s/%(name)s/ipv6route'

    def __init__(self, route_name, base_etcnet_dir):
        super(Route, self).__init__()
        self.last_idx = 1
        self.has_set_default_ipv4 = False
        self.has_set_default_ipv6 = False
        self._route_name = route_name
        self._base_etcnet_dir = base_etcnet_dir

    def copy(self):
        r = Route(self._route_name, self._base_etcnet_dir)
        r._conf = self._conf.copy()
        r.last_idx = self.last_idx
        r.has_set_default_ipv4 = self.has_set_default_ipv4
        r.has_set_default_ipv6 = self.has_set_default_ipv6
        return r

    @property
    def path(self):
        return self.route_fn_tpl % ({'base': self._base_etcnet_dir,
                                     'name': self._route_name})


class NetInterface(ConfigMap):
    """Represents a net/ifaces (and its config + children)."""

    iface_fn_tpl = '%(base)s/%(name)s/options'

    iface_types = {
        'ethernet': 'eth',
        'bond': 'bond',
        'bridge': 'bri',
    }

    def __init__(self, iface_name, base_etcnet_dir, kind='ethernet'):
        super(NetInterface, self).__init__()
        self.children = []
        self.routes = Route(iface_name, base_etcnet_dir)
        self.kind = kind

        self._iface_name = iface_name
#        self._conf['DEVICE'] = iface_name
        self._base_etcnet_dir = base_etcnet_dir

    @property
    def name(self):
        return self._iface_name

#    @name.setter
#    def name(self, iface_name):
#        self._iface_name = iface_name
#        self._conf['DEVICE'] = iface_name

    @property
    def kind(self):
        return self._kind

    @kind.setter
    def kind(self, kind):
        if kind not in self.iface_types:
            raise ValueError(kind)
        self._kind = kind
        self._conf['TYPE'] = self.iface_types[kind]

    @property
    def path(self):
        return self.iface_fn_tpl % ({'base': self._base_etcnet_dir,
                                     'name': self.name})

    def copy(self, copy_children=False, copy_routes=False):
        c = NetInterface(self.name, self._base_etcnet_dir, kind=self._kind)
        c._conf = self._conf.copy()
        if copy_children:
            c.children = list(self.children)
        if copy_routes:
            c.routes = self.routes.copy()
        return c


class Renderer(renderer.Renderer):
    """Renders network information in a /etc/sysconfig format."""

    iface_defaults = tuple([
        ('ONBOOT', True),
        ('DISABLED', False),
        ('NM_CONTROLLED', False),
        ('BOOTPROTO', 'dhcp'),
    ])

    def __init__(self, config=None):
        if not config:
            config = {}
        self.etcnet_dir = config.get('etcnet_dir', 'etc/net/ifaces/')
        self.netrules_path = config.get(
            'netrules_path', 'etc/udev/rules.d/70-persistent-net.rules')
        self.dns_path = config.get('dns_path', 'etc/resolv.conf')

    @classmethod
    def _render_iface_shared(cls, iface, iface_cfg):
        for k, v in cls.iface_defaults:
            iface_cfg[k] = v

#        for (old_key, new_key) in [('mac_address', 'HWADDR'), ('mtu', 'MTU')]:
#            old_value = iface.get(old_key)
#            if old_value is not None:
#                iface_cfg[new_key] = old_value

    @classmethod
    def _render_physical_interfaces(cls, network_state, iface_contents):
        physical_filter = renderer.filter_by_physical
        for iface in network_state.iter_interfaces(physical_filter):
            iface_name = iface['name']
#            iface_subnets = iface.get("subnets", [])
            iface_cfg = iface_contents[iface_name]
            route_cfg = iface_cfg.routes
#            if len(iface_subnets) == 1:
#                cls._render_subnet(iface_cfg, route_cfg, iface_subnets[0])
#            elif len(iface_subnets) > 1:
#                for i, isubnet in enumerate(iface_subnets,
#                                            start=len(iface_cfg.children)):
#                    iface_sub_cfg = iface_cfg.copy()
#                    iface_sub_cfg.name = "%s:%s" % (iface_name, i)
#                    iface_cfg.children.append(iface_sub_cfg)
#                    cls._render_subnet(iface_sub_cfg, route_cfg, isubnet)

    @staticmethod
    def _render_dns(network_state, existing_dns_path=None):
        content = resolv_conf.ResolvConf("")
        if existing_dns_path and os.path.isfile(existing_dns_path):
            content = resolv_conf.ResolvConf(util.load_file(existing_dns_path))
        for nameserver in network_state.dns_nameservers:
            content.add_nameserver(nameserver)
        for searchdomain in network_state.dns_searchdomains:
            content.add_search_domain(searchdomain)
        return "\n".join([_make_header(';'), str(content)])


    @classmethod
    def _render_etcnet(cls, base_etcnet_dir, network_state):
        '''Given state, return /etc/net files + contents'''
        iface_contents = {}
        for iface in network_state.iter_interfaces():
            if iface['type'] == "loopback":
                continue
            iface_name = iface['name']
            iface_cfg = NetInterface(iface_name, base_etcnet_dir)
            cls._render_iface_shared(iface, iface_cfg)
            iface_contents[iface_name] = iface_cfg
        cls._render_physical_interfaces(network_state, iface_contents)
#        cls._render_bond_interfaces(network_state, iface_contents)
#        cls._render_vlan_interfaces(network_state, iface_contents)
#        cls._render_bridge_interfaces(network_state, iface_contents)
        contents = {}
        for iface_name, iface_cfg in iface_contents.items():
            if iface_cfg or iface_cfg.children:
                contents[iface_cfg.path] = iface_cfg.to_string()
                for iface_cfg in iface_cfg.children:
                    if iface_cfg:
                        contents[iface_cfg.path] = iface_cfg.to_string()
            if iface_cfg.routes:
                contents[iface_cfg.routes.path] = iface_cfg.routes.to_string()
        return contents

    def render_network_state(self, network_state, target=None):
        base_etcnet_dir = util.target_path(target, self.etcnet_dir)
        for path, data in self._render_etcnet(base_etcnet_dir,
                                                 network_state).items():
            util.write_file(path, data)
        if self.dns_path:
            dns_path = util.target_path(target, self.dns_path)
            resolv_content = self._render_dns(network_state,
                                              existing_dns_path=dns_path)
            util.write_file(dns_path, resolv_content)
        if self.netrules_path:
            netrules_content = self._render_persistent_net(network_state)
            netrules_path = util.target_path(target, self.netrules_path)
            util.write_file(netrules_path, netrules_content)


def available(target=None):
    expected = ['ifup', 'ifdown']
    search = ['/sbin', '/usr/sbin']
    for p in expected:
        if not util.which(p, search=search, target=target):
            return False

    expected_paths = [
        'etc/net/scripts/functions',
        'etc/net/scripts/functions-eth',
        'etc/net/scripts/functions-ip',
        'etc/net/scripts/functions-ipv4',
        'etc/net/scripts/functions-ipv6',
        'etc/net/scripts/functions-vlan',
        'etc/net/scripts/ifdown']
    for p in expected_paths:
        if not os.path.isfile(util.target_path(target, p)):
            return False
    return True


# vi: ts=4 expandtab
