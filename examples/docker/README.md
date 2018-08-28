# Prerequisites #
To run the docker example one has to have docker-ce installed and accessible
via "unix:///var/run/docker.sock". The default docker bridge network also
needs to be accesible from the pytest executor since the test tries to
establish a ssh connection to the container.

Successfully tested against Docker version 17.12.1-ce, build 7390fc6. 
But it should work with later versions aswell.
