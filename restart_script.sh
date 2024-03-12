#!/bin/bash

# Define the current date and time
current_datetime=$(date +"%Y-%m-%d_%H-%M-%S")

# SSH into the server, rename the file, and restart the service
ssh -i "om-key.pem" ubuntu@ec2-54-196-92-178.compute-1.amazonaws.com <<EOF
    # Rename the log file
    mv /home/ubuntu/Copy-Trading-API/wrapper.log /home/ubuntu/Copy-Trading-API/wrapper_${current_datetime}.log
    
    # Restart the service
    sudo systemctl restart trade
EOF
