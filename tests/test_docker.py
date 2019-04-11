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

from labgrid import Environment
from labgrid.driver import DockerDriver
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
def env_with_docker_shell_strategy(tmp_path_factory):
    p = tmp_path_factory.mktemp("docker") / "config.yaml"
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


def test_driver_use_network_service(target_with_docker_shell_strategy, mocker):
    """Test activation of DockerDriver instance and subsequent invocation of on() and use of network_service"""

    # Shorthand for easing subsequent use
    t = target_with_docker_shell_strategy

    # Get strategy - which leads to DockerDriver creation, activation and registration
    strategy = t.get_driver("DockerShellStrategy")

    # Strategy will call activate(), then on(); mock derived calls for each
    # on_activate(), mock:
    #   DockerClient.__init__()             - dockerdriver.py        -> use mocker.create_autospec()
    #   _client.images.pull()               - dockerdriver.py
    #   _client.api.create_container()      - dockerdriver.py
    # on(), mock:
    #   _client.api.start()                 - dockerdriver.py
    #
    # Then "command" fixture will bind and activate SSHDriver
    # SSHDriver.super.__init__()
    #   bind_resource()                     - target.py
    # on_client_bound(), mock
    #   target_factory.make_resource()      - docker.py
    # on_poll(), mock:
    #   _client.api.containers()            - docker.py
    #   socket.create_connection()          - docker.py
    #
    # Finally, command.run will execute command on target and get results - but mock this?
    #

    strategy.transition("shell")

    # Find shorthands for objects we want to make assertions about
    dd = t.drivers[0]
    dc_mock = dd._client
    api_mock = dc_mock.api

    # Assert what mock calls transitioning to "shell" must have caused
    # DockerDriver::on_activate():
    dc_mock.images.pull.assert_called_once()
    api_mock.create_host_config.assert_called_once()
    api_mock.create_container.assert_called_once()

    # TODO-ANGA: More assertions on that .transition("shell") did

    # TODO-ANGA: Also describe what happens when a network_service is created

    print('hej')
