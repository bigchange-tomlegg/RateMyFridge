#!/usr/bin/env bash
curl -X POST "$RATE_MY_FRIDGE_URL/rate-fridge" \
  -F "image=@fridge.jpg"
