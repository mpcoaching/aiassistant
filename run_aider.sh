#!/bin/bash
# Explicitly clear out all incoming arguments sent by the broken extension
set -- 

# Run your clean command directly to your actual config file
aider --config "./ai-assistant-infra/configs/aider/.aider.conf.yml"
