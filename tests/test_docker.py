import pytest

from labgrid.driver import DockerDriver
from labgrid import Environment

@pytest.fixture
def docker_env(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
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

@pytest.fixture
def docker_target(docker_env):
    return docker_env.get_target()

#@pytest.fixture
#def qemu_driver(qemu_target):
#    q = QEMUDriver(
#        qemu_target,
#        "qemu",
#        qemu_bin="qemu",
#        machine='',
#        cpu='',
#        memory='',
#        boot_args='',
#        extra_args='',
#        kernel='kernel',
#        rootfs='rootfs')
#    return q

@pytest.fixture
def command(docker_target):
    strategy = docker_target.get_driver('DockerShellStrategy')
    strategy.transition("shell")
    shell = docker_target.get_driver('CommandProtocol')
    return shell

def test_shell(command):
    print('hello')
    stdout, stderr, returncode = command.run('cat /proc/version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'Linux' in stdout[0]

    stdout, stderr, returncode = command.run('false')
    assert returncode != 0
    assert len(stdout) == 0
    assert len(stderr) == 0
