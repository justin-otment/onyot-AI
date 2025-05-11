#!/bin/bash
docker run --rm --cap-add=NET_ADMIN --device /dev/net/tun onyot-ai
