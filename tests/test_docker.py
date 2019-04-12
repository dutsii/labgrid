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
     _client
      * driver/dockerdriver.py:75:  .images.pull()
     _client.api
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
import logging

from labgrid import Environment
from labgrid.driver import DockerDriver
from labgrid.resource.docker import DockerConstants
from labgrid.exceptions import NoResourceFoundError


@pytest.fixture(scope='function')
def env_with_docker_driver(tmp_path_factory):
    p = tmp_path_factory.mktemp("docker") / "config.yaml"
    p.write_text(docker_yaml.yaml_no_shell_strategy)
    return Environment(str(p))


@pytest.fixture(scope='function')
def target_with_docker_driver(env_with_docker_driver):
    return env_with_docker_driver.get_target()


@pytest.fixture(scope='function')
def env_with_docker_shell_strategy(tmp_path_factory, mocker):
    # TODO-ANGA: Move to test itself
    # Force target.py::update_resources() to take real action - always
    time_monotonic = mocker.patch('labgrid.target.monotonic')
    time_monotonic.side_effect = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    p = tmp_path_factory.mktemp("docker") / "config.yaml"
    # TODO-ANGA: No need for using a yaml file with the SSHDriver
    p.write_text(docker_yaml.yaml_all)
    return Environment(str(p))


@pytest.fixture(scope='function')
def target_with_docker_shell_strategy(env_with_docker_shell_strategy, mocker):

    # Mock actions on the imported "docker" python module
    docker_client_class = mocker.patch('docker.DockerClient', autospec=True)
    docker_client = docker_client_class.return_value

    api_client_class = mocker.patch('docker.api.client.APIClient', autospec=True)
    docker_client.api = api_client_class.return_value
    docker_client.api.base_url = "unix:///var/run/docker.sock"

    # Mock actions on the imported "socket" python module
    socket_create_connection = mocker.patch('socket.create_connection')
    connection = mocker.MagicMock
    socket_create_connection.side_effect = [Exception('No connection on first call'), connection]

    return env_with_docker_shell_strategy.get_target()


def test_create_driver_fail_missing_docker_daemon(target):
    """The test target does not contain any DockerDaemon instance - and so creation must fail"""
    with pytest.raises(NoResourceFoundError):
        DockerDriver(target, "docker_driver")


# def test_create_driver(target_with_docker_driver):
#     """Target with a DockerDaemon instance allows driver creation to go through.
#     Note: It is crucial for this test that attribute network_services is defined in the
#     .yaml file: DockerDaemon::on_client_bound() expects at least one such service to be present.
#     """
#     dd = target_with_docker_driver.get_driver(DockerDriver)
#     assert isinstance(dd, DockerDriver)


def test_driver_use_network_service(env_with_docker_shell_strategy, mocker):
    """Test activation of DockerDriver instance and subsequent invocation of on() and use of network_service"""

    logger = logging.getLogger('TestDocker')

    # Mock actions on the imported "docker" python module
    docker_client_class = mocker.patch('docker.DockerClient', autospec=True)
    docker_client = docker_client_class.return_value

    api_client_class = mocker.patch('docker.api.client.APIClient', autospec=True)
    docker_client.api = api_client_class.return_value
    api_client = docker_client.api
    api_client.base_url = "unix:///var/run/docker.sock"
    # First, empty, list is delivered by ...api.containers() when DockerDaemon tries
    # to clean up old containers. Second, one-item, list is delivered by ...api.containers()
    # that is part of DockerDaemon::update_resources() - it is cached for future use; therefore
    # no need to replicate it.
    api_client.containers.side_effect = [
        [],
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

    # get_target() - which calls make_target() - creates resources/drivers from .yaml configured
    # environment. Creation provokes binding and attempts to connect to network services.
    t = env_with_docker_shell_strategy.get_target()

    # So far no socket connect attempts were successful (actually expressed by what happens next)
    sock.shutdown.assert_not_called()
    sock.close.assert_not_called()

    # Get strategy - needed to transition to "shell" state - which activates DockerDriver and calls on()
    logger.debug('Before get_driver()')
    strategy = t.get_driver("DockerShellStrategy")

    # strategy starts in state "unknown" so the following should be a no-op
    strategy.transition("unknown")

    # Then actual action happens. The strategy transition
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
    # which make use of the SSHDriver.  Binding the SSHDriver is important since
    # it triggers activation of the NetworkService. But then SSHDriver uses ssh
    # to connect to the NetworkService which will lead to error.
    # So let's just use a mock that accepts anything.

    # Call t.update_resource() directly instead of trying to create e.g. an SSHDriver
    # on top of the NetworkService which - in the case of SSHDriver - would lead
    # to a real "ssh" trying to connect to the NetworkService. This wouldn't work
    # (since the NetworkService isn't real) and really doesn't have to do with the
    # docker driver implementation.
    t.update_resources()

    # This time socket connection was successful (per the third socket_create_connection
    # return value defined above.
    sock.shutdown.assert_called_once()
    sock.close.assert_called_once()

    # Test what happens if taking a forbidden strategy transition; "shell" -> "unknown"
    from labgrid.strategy import StrategyError
    with pytest.raises(StrategyError):
        strategy.transition("unknown")

    # How are invalid state names handled?
    with pytest.raises(KeyError):
        strategy.transition("this is not a valid state")

    # Return to "off" state - to also use that part of the DockerDriver code.
    strategy.transition("off")
