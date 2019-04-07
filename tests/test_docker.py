"""
Test what?

  * Basic creation of DockerDriver()
  * Cleanup of docker containers
  * The example from .../example/docker/test_shell.py
  * The cycle() method.
  *
"""



import pytest

from labgrid.driver import DockerDriver
from labgrid import Environment

@pytest.fixture(scope='session')
def docker_env(tmp_path_factory):
    p = tmp_path_factory.mktemp("docker") / "config.yaml"
    p.write_text(
        """
        targets:
          main:
            resources:
              - DockerDaemon:
                  docker_daemon_url: "unix:///var/run/docker.sock"
            drivers:
              - DockerDriver:
                  image_uri: "rastasheep/ubuntu-sshd:16.04"
                  container_name: "ubuntu-lg-example"
                  host_config: {"network_mode":"bridge"}
                  network_services: [{"port":22,"username":"root","password":"root"}]
              - DockerShellStrategy: {}
              - SSHDriver:
                  keyfile: ""
        """
    )
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
