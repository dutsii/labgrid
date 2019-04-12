import pytest

from labgrid import Environment
from labgrid.driver import DockerDriver
from labgrid.resource.docker import DockerConstants
from labgrid.exceptions import NoResourceFoundError


def check_daemon_presence():
    try:
        import docker
        dock = docker.from_env()
        dock.info()
    except OSError:
        return False
    return True


@pytest.fixture
def docker_env(tmp_path_factory):
    p = tmp_path_factory.mktemp("docker") / "config.yaml"
    # Note: The SSHDriver part at bottom is only used by the test that will run
    # if a docker daemon is present, not by test_driver_without_daemon
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
                host_config: {"network_mode": "bridge"}
                network_services: [{"port": 22, "username": "root", "password": "root"}]
            - DockerShellStrategy: {}
            - SSHDriver:
                keyfile: ""
        """
    )
    return Environment(str(p))


@pytest.fixture
def docker_target(docker_env):
    return docker_env.get_target()


@pytest.fixture
def command(docker_target):
    strategy = docker_target.get_driver('DockerShellStrategy')
    strategy.transition("shell")
    shell = docker_target.get_driver('CommandProtocol')
    yield shell
    strategy.transition("off")


# test_docker_with_daemon tests the docker machine when a real docker daemon is running.
# If not it is skipped. The test also makes use of other parts of labgrid - especially
# the SSHDriver.
@pytest.mark.skipif(not check_daemon_presence(), reason="No access to a docker daemon")
def test_docker_with_daemon(command):
    stdout, stderr, returncode = command.run('cat /proc/version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'Linux' in stdout[0]

    stdout, stderr, returncode = command.run('false')
    assert returncode != 0
    assert len(stdout) == 0
    assert len(stderr) == 0

# Just a very basic test for proper failure on illegal configuration.
def test_create_driver_fail_missing_docker_daemon(target):
    """The test target does not contain any DockerDaemon instance - and so creation must fail"""
    with pytest.raises(NoResourceFoundError):
        DockerDriver(target, "docker_driver")

# This test simulates actions in test_docker_with_daemon, but with mocks inserted for
# operations provided by the python docker module, the python socket module - and time.
def test_docker_without_daemon(docker_env, mocker):
    """Test as many aspects as possible of DockerDriver, DockerDaemon, DockerManager
    and DockerShellStrategy without using an actual docker daemon, real sockets of system time"""

    # TODO-ANGA: This must be better understood. Provide better explanation!
    # Fake: In real life ResourceManager is intended to be a singleton; here we force it to start over again
    from labgrid.resource import ResourceManager
    ResourceManager.instances = {}

    # Target::update_resources() and Target::await_resources use time.monotonic() and
    # time.sleep() to control when to search for resources. Avoid time delays and make
    # running from cmd-line and inside debugger equal by mocking out all time.
    time_monotonic = mocker.patch('labgrid.target.monotonic')
    time_monotonic.side_effect = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    # Mock actions on the imported "docker" python module
    docker_client_class = mocker.patch('docker.DockerClient', autospec=True)
    docker_client = docker_client_class.return_value
    api_client_class = mocker.patch('docker.api.client.APIClient', autospec=True)
    docker_client.api = api_client_class.return_value
    api_client = docker_client.api
    api_client.base_url = "unix:///var/run/docker.sock"
    # First, a "mocked" old docker container is returned by ...api.containers(); this is done
    # when DockerDaemon tries to clean up old containers. Next, a one-item list is delivered by
    # ...api.containers() which is part of DockerDaemon::update_resources() - it is cached
    # for future use; therefore no need to replicate this entry in the side_effects list.
    api_client.containers.side_effect = [
        [{'Labels': {DockerConstants.DOCKER_LG_CLEANUP_LABEL: DockerConstants.DOCKER_LG_CLEANUP_TYPE_AUTO},
          'NetworkSettings': {'IPAddress': '1.1.1.1'},
          'Names': 'old-one',
          'Id': '0'
          }],
        [{'Labels': {DockerConstants.DOCKER_LG_CLEANUP_LABEL: DockerConstants.DOCKER_LG_CLEANUP_TYPE_AUTO},
          'NetworkSettings': {'IPAddress': '2.1.1.1'},
          'Names': 'actual-one',
          'Id': '1'
          }]
    ]

    # Mock actions on the imported "socket" python module
    socket_create_connection = mocker.patch('socket.create_connection')
    sock = mocker.MagicMock()
    # First two negative connection setup attempts are used at initial resource setup during
    # strategy.transition("shell"); these simulate that it takes time for the docker container
    # to come up. The final, successful, return value is delivered when t.update_resources()
    # is called explicitly later on.
    socket_create_connection.side_effect = [Exception('No connection on first call'),
                                            Exception('No connection on second call'),
                                            sock]

    # get_target() - which calls make_target() - creates resources/drivers from .yaml
    # configured environment. Creation provokes binding and attempts to connect
    # to network services.
    api_client.remove_container.assert_not_called()
    t = docker_env.get_target()
    api_client.remove_container.assert_called_once()

    # Make sure DockerDriver didn't accidentally succeed with a socket connect attempt
    # (this fact is actually expressed by what happens next - the socket is closed).
    sock.shutdown.assert_not_called()
    sock.close.assert_not_called()

    # Get strategy - needed to transition to "shell" state.
    strategy = t.get_driver("DockerShellStrategy")

    # strategy starts in state "unknown" so the following should be a no-op
    strategy.transition("unknown")

    # Now activate DockerDriver and set it "on". This creates and starts a (mocked) container
    strategy.transition("shell")

    # Assert what mock calls transitioning to "shell" must have caused
    #
    # DockerDriver::on_activate():
    docker_client.images.pull.assert_called_once()
    api_client.create_host_config.assert_called_once()
    api_client.create_container.assert_called_once()
    #
    # DockerDriver::on()
    api_client.start.assert_called_once()

    # From here the test using the real docker daemon would proceed with
    #   shell = t.get_driver('CommandProtocol')
    #   shell.run('...')
    # which makes use of e.g. the SSHDriver.  Binding the SSHDriver is important since
    # it triggers activation of the NetworkService. But then SSHDriver uses ssh
    # to connect to the NetworkService which will lead to error.
    # Instead just call update_resources() directly - which is what is needed to
    # provoke DockerDaemon to create a new NetworkService instance.
    t.update_resources()

    # This time socket connection was successful (per the third socket_create_connection
    # return value defined above).
    sock.shutdown.assert_called_once()
    sock.close.assert_called_once()

    # Bonus: Test what happens if taking a forbidden strategy transition; "shell" -> "unknown"
    from labgrid.strategy import StrategyError
    with pytest.raises(StrategyError):
        strategy.transition("unknown")

    # Also bonus: How are invalid state names handled?
    with pytest.raises(KeyError):
        strategy.transition("this is not a valid state")

    # Return to "off" state - to also use that part of the DockerDriver code.
    strategy.transition("off")
    from labgrid.strategy.shellstrategy import Status
    assert strategy.status == Status.off
