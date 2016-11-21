# vi: ts=4 expandtab
#
#    Copyright (C) 2012 Yahoo! Inc.
#
#    Author: Joshua Harlow <harlowja@yahoo-inc.com>
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

"""
Write Files
-----------
**Summary:** write arbitrary files

Write out arbitrary content to files, optionally setting permissions. Content
can be specified in plain text or binary. Data encoded with either base64 or
binary gzip data can be specified and will be decoded before being written.

.. note::
    if multiline data is provided, care should be taken to ensure that it
    follows yaml formatting standargs. to specify binary data, use the yaml
    option ``!!binary``

**Internal name:** ``cc_write_files``

**Module frequency:** per instance

**Supported distros:** all

**Config keys**::

    write_files:
        - encoding: b64
          content: CiMgVGhpcyBmaWxlIGNvbnRyb2xzIHRoZSBzdGF0ZSBvZiBTRUxpbnV4...
          owner: root:root
          path: /etc/sysconfig/selinux
          permissions: '0644'
        - content: |
            # My new /etc/sysconfig/samba file

            SMDBOPTIONS="-D"
          path: /etc/sysconfig/samba
        - content: !!binary |
            f0VMRgIBAQAAAAAAAAAAAAIAPgABAAAAwARAAAAAAABAAAAAAAAAAJAVAAAAAA
            AEAAHgAdAAYAAAAFAAAAQAAAAAAAAABAAEAAAAAAAEAAQAAAAAAAwAEAAAAAAA
            AAAAAAAAAwAAAAQAAAAAAgAAAAAAAAACQAAAAAAAAAJAAAAAAAAcAAAAAAAAAB
            ...
          path: /bin/arch
          permissions: '0555'
"""

import base64
import os
import six

from cloudinit.settings import PER_INSTANCE
from cloudinit import util

frequency = PER_INSTANCE

DEFAULT_OWNER = "root:root"
DEFAULT_PERMS = 0o644
UNKNOWN_ENC = 'text/plain'


def handle(name, cfg, _cloud, log, _args):
    files = cfg.get('write_files')
    if not files:
        log.debug(("Skipping module named %s,"
                   " no/empty 'write_files' key in configuration"), name)
        return
    write_files(name, files, log)


def canonicalize_extraction(encoding_type, log):
    if not encoding_type:
        encoding_type = ''
    encoding_type = encoding_type.lower().strip()
    if encoding_type in ['gz', 'gzip']:
        return ['application/x-gzip']
    if encoding_type in ['gz+base64', 'gzip+base64', 'gz+b64', 'gzip+b64']:
        return ['application/base64', 'application/x-gzip']
    # Yaml already encodes binary data as base64 if it is given to the
    # yaml file as binary, so those will be automatically decoded for you.
    # But the above b64 is just for people that are more 'comfortable'
    # specifing it manually (which might be a possiblity)
    if encoding_type in ['b64', 'base64']:
        return ['application/base64']
    if encoding_type:
        log.warn("Unknown encoding type %s, assuming %s",
                 encoding_type, UNKNOWN_ENC)
    return [UNKNOWN_ENC]


def write_files(name, files, log):
    if not files:
        return

    for (i, f_info) in enumerate(files):
        path = f_info.get('path')
        if not path:
            log.warn("No path provided to write for entry %s in module %s",
                     i + 1, name)
            continue
        path = os.path.abspath(path)
        extractions = canonicalize_extraction(f_info.get('encoding'), log)
        contents = extract_contents(f_info.get('content', ''), extractions)
        (u, g) = util.extract_usergroup(f_info.get('owner', DEFAULT_OWNER))
        perms = decode_perms(f_info.get('permissions'), DEFAULT_PERMS, log)
        util.write_file(path, contents, mode=perms)
        util.chownbyname(path, u, g)


def decode_perms(perm, default, log):
    if perm is None:
        return default
    try:
        if isinstance(perm, six.integer_types + (float,)):
            # Just 'downcast' it (if a float)
            return int(perm)
        else:
            # Force to string and try octal conversion
            return int(str(perm), 8)
    except (TypeError, ValueError):
        log.warn("Undecodable permissions %s, assuming %s", perm, default)
        return default


def extract_contents(contents, extraction_types):
    result = contents
    for t in extraction_types:
        if t == 'application/x-gzip':
            result = util.decomp_gzip(result, quiet=False, decode=False)
        elif t == 'application/base64':
            result = base64.b64decode(result)
        elif t == UNKNOWN_ENC:
            pass
    return result
