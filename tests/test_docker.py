"""
Test what?

  * Basic creation of DockerDriver()
  * Cleanup of docker containers
  * The example from .../example/docker/test_shell.py
  * The cycle() method.
  *
  * Two calls to docker module must be mocked:
  *   * resource/docker.py:40:docker.DockerClient
  *   * driver/dockerdriver.py:74:docker.DockerClient
  * Besides calls to the created [docker]_client must be mocked:
      * resource/docker.py:53:      .base_url
      * resource/docker.py:54:      .containers()
      * resource/docker.py:59:      .remove_container()
      * resource/docker.py:113:     .containers()
      * driver/dockerdriver.py:77:  .create_container()
      * driver/dockerdriver.py:86:  .create_host_config()
      * driver/dockerdriver.py:91:  .remove_container()
      * driver/dockerdriver.py:98:  .start()
      * driver/dockerdriver.py:102: .stop()
  * Finally we should probably fake that SSHDriver can work as expected
  * - or at least the discovery of the NetworkService that it depends on.
  * Therefore also mock:
      * socket.connect()
"""

import pytest
import docker_yaml

from labgrid import Environment

@pytest.fixture(scope='session')
def docker_env(tmp_path_factory):
    p = tmp_path_factory.mktemp("docker") / "config.yaml"
    p.write_text(docker_yaml.yaml_all)
    return Environment(str(p))

@pytest.fixture(scope='session')
def docker_target(docker_env):
    return docker_env.get_target()

@pytest.fixture(scope='session')
def command(docker_target):
    strategy = docker_target.get_driver('DockerShellStrategy')
    strategy.transition("shell")
    shell = docker_target.get_driver('CommandProtocol')
    yield shell
    strategy.transition("off")

#def test_create_driver_fail_missing_docker_daemon(self, target):
#    """target does not contain any DockerDaemon instance - and so creation must fail"""
#    with pytest.raises(NoResourceFoundError):
#        DockerDriver(target, "ssh")

#def test_create_driver(self, target):
#    """target does not contain any DockerDaemon instance - and so creation must fail"""
#    with pytest.raises(NoResourceFoundError):
#        DockerDriver(target, "ssh")

#def test_activate_driver(self, target):
#    """target does not contain any DockerDaemon instance - and so creation must fail"""
#    with pytest.raises(NoResourceFoundError):
#        DockerDriver(target, "ssh")

#def test_driver_set_on(self, target):
#    """target does not contain any DockerDaemon instance - and so creation must fail"""
#    with pytest.raises(NoResourceFoundError):
#        DockerDriver(target, "ssh")



def test_shell(command):
    stdout, stderr, returncode = command.run('cat /proc/version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'Linux' in stdout[0]

    stdout, stderr, returncode = command.run('false')
    assert returncode != 0
    assert len(stdout) == 0
    assert len(stderr) == 0

def test_again(command):
    stdout, stderr, returncode = command.run('false')
    assert returncode != 0
    assert len(stdout) == 0
    assert len(stderr) == 0
