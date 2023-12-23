#!/bin/bash
sudo -u $SUDO_UID echo "Setting up pool-ubuntu."
sudo -u $SUDO_UID echo "Installing required python packages."
sudo -u $SUDO_UID pip3 install -r ${BASEDIR}/setup/requirements.txt
sudo -u $SUDO_UID echo "Configuring systemd."
cp ${BASEDIR}/setup/poolpi_ubuntu.service /etc/systemd/system/poolpi_ubuntu.service
chmod 644 /etc/systemd/system/poolpi_ubuntu.service
systemctl daemon-reload
systemctl enable redis-server
systemctl enable --now poolpi_ubuntu.service
sudo -u $SUDO_UID echo "Setup script complete."