#!/bin/bash

# SSH into the server and restart the service
ssh -i "om-key.pem" ubuntu@ec2-54-196-92-178.compute-1.amazonaws.com <<EOF
    sudo systemctl restart trade
EOF
