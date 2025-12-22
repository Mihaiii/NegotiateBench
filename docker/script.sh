#!/bin/bash

cd NegotiateBench
python runner.py &
uvicorn website:app --port 7860 --host 0.0.0.0