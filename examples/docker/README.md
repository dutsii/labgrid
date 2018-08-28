# Prerequisites #
To run the docker example one has to have docker-ce installed and accessible
via "unix:///var/run/docker.sock". The default docker bridge network also
needs to be accessible from the pytest executor since the test tries to
establish an ssh connection to the container.

Successfully tested against Docker version 18.06.1-ce, build e68fc7a.
But it should work with later versions as well.
