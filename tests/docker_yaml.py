import textwrap

# Function derive_yaml() and the subsequent verbatim string definitions are
# used to set up various configuration files used during test.
def derive_yaml(docker_resources="", docker_drivers="", docker_strategies="", network_drivers=""):
    yaml_fragment = \
        """\
        targets:
          main:
            resources:
{docker_resources}
            drivers:
{docker_drivers}
{docker_strategies}
{network_drivers}
        """.format(docker_resources=docker_resources,
                   docker_drivers=docker_drivers,
                   docker_strategies=docker_strategies,
                   network_drivers=network_drivers)
    return textwrap.dedent(yaml_fragment)


docker_daemon_cfg = \
    """\
              - DockerDaemon:
                  docker_daemon_url: "unix:///var/run/docker.sock"
    """
docker_driver_cfg = \
    """\
              - DockerDriver:
                  image_uri: "rastasheep/ubuntu-sshd:16.04"
                  container_name: "ubuntu-lg-example"
                  host_config: {"network_mode":"bridge"}
                  network_services: [{"port":22,"username":"root","password":"root"}]
    """
docker_shell_strategy_cfg = \
    """\
              - DockerShellStrategy: {}
    """
sshdriver_cfg = \
    """\
              - SSHDriver:
                  keyfile: ""
    """

yaml_no_docker_daemon = derive_yaml()
yaml_no_shell_strategy = derive_yaml(docker_daemon_cfg, docker_driver_cfg)
yaml_no_ssh_driver = derive_yaml(docker_daemon_cfg, docker_driver_cfg, docker_shell_strategy_cfg)
yaml_all = derive_yaml(docker_daemon_cfg, docker_driver_cfg, docker_shell_strategy_cfg, sshdriver_cfg)
