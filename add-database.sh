#!/bin/bash

cd ~/devilbox
echo "VHOST NAME: $1"
bash -c "sudo docker-compose exec --user devilbox php sh -c \"mysql -h localhost -P 3306 --protocol=tcp -u root -e 'CREATE DATABASE $1' \" "
exit 1

#-h mysql -u root -p
#echo "Entered MySQL shell"
#CREATE DATABASE "$1"
#echo "Created database"