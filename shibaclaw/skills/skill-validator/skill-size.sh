#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <skill_path>"
  exit 1
fi

SKILL_PATH="$1"

if [ ! -d "$SKILL_PATH" ]; then
  echo "Error: Skill path '$SKILL_PATH' is not a directory."
  exit 1
fi

du -sh "$SKILL_PATH" | awk '{print $1}'
