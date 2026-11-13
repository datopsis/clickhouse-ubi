"""Share the digest-pinned UBI builder's repository configuration with admission."""
import hashlib
from pathlib import Path

RPM_ARCH = {'amd64': 'x86_64', 'arm64': 'aarch64'}
EXPECTED_REPOS = {'ubi-9-baseos-rpms', 'ubi-9-appstream-rpms'}


def configure(base, directory, architecture):
    for name in ('root', 'cache', 'log', 'persist'):
        Path(directory, name).mkdir()
    base.conf.read()
    base.conf.installroot = directory + '/root'
    base.conf.cachedir = directory + '/cache'
    base.conf.logdir = directory + '/log'
    base.conf.persistdir = directory + '/persist'
    base.conf.install_weak_deps = False
    base.conf.arch = RPM_ARCH[architecture]
    base.conf.ignorearch = True
    base.conf.substitutions['arch'] = RPM_ARCH[architecture]
    base.conf.substitutions['basearch'] = RPM_ARCH[architecture]
    base.conf.substitutions['releasever'] = '9'
    base.conf.module_platform_id = 'platform:el9'
    base.read_all_repos()
    enabled = list(base.repos.iter_enabled())
    if {repo.id for repo in enabled} != EXPECTED_REPOS:
        raise ValueError('missing or unexpected enabled UBI repositories')
    configs = {}
    urls = {}
    for repo in enabled:
        if not repo.gpgcheck or not repo.baseurl or repo.mirrorlist or repo.metalink:
            raise ValueError('invalid UBI repository configuration')
        configs[repo.repofile] = hashlib.sha256(Path(repo.repofile).read_bytes()).hexdigest()
        urls[repo.id] = list(repo.baseurl)
        repo.skip_if_unavailable = False
        repo.metadata_expire = 0
        repo.timeout = 30
        repo.retries = 1
    base.fill_sack(load_system_repo=False)
    for repo in enabled:
        if not base.sack.query().available().filter(reponame=repo.id):
            raise ValueError(f'missing or empty repository: {repo.id}')
    return {'config_sha256': configs, 'urls': urls}
