import os
import re

import pytest

from pyhttpd.conf import HttpdConf

# `httpd -M` reports modules as "name_module (static|shared)"; mod_info.c
# renders modules by their actual source filename, which is "mod_<name>.c"
# except for a few that don't follow that pattern.
MODULE_FILE_OVERRIDES = {"core": "core.c", "http": "http_core.c"}
MPM_FILES = {
    "event": "event.c", "worker": "worker.c", "prefork": "prefork.c",
    "motorz": "motorz.c", "simple": "simple_api.c",
}


def module_file(name):
    if name.startswith("mpm_"):
        return MPM_FILES.get(name[len("mpm_"):], f"mod_{name}.c")
    return MODULE_FILE_OVERRIDES.get(name, f"mod_{name}.c")


class TestInfo:
    """mod_info: /server-info lists every loaded module."""

    @pytest.fixture(autouse=True, scope='class')
    def _class_scope(self, env):
        conf = HttpdConf(env, extras={
            'base': """
        <Location "/server-info">
            SetHandler server-info
        </Location>
        """
        })
        conf.add_vhost_test1()
        conf.install()
        assert env.apache_restart() == 0

    def loaded_modules(self, env):
        httpd = os.path.join(env.bin_dir, 'httpd')
        conf = os.path.join(env.server_dir, 'conf', 'httpd.conf')
        r = env.run([httpd, "-d", env.server_dir, "-f", conf, "-M"])
        names = re.findall(r'^\s*(\w+)_module\b', r.stdout, re.M)
        return {module_file(n) for n in names}

    def test_generators_002_01_modules_listed(self, env):
        r = env.curl_get(env.mkurl("http", "test1", "/server-info"))
        assert r.response["status"] == 200
        body = r.response["body"].decode()
        listed = set(re.findall(r'<a name="(\w+\.c)">', body))
        expected = self.loaded_modules(env)
        missing = expected - listed
        extra = listed - expected
        assert not missing and not extra, \
            f"missing: {sorted(missing)}, unexpected: {sorted(extra)}"
