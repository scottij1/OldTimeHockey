#!/bin/bash
while true; do
	until python3 DiscordBot_Updated.py soft; do
		echo "DiscordBot crashed. Respawning."
		sleep 1
	done
done

