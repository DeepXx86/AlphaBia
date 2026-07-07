#!/bin/bash
cd /mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk
python3 test/engine_match.py --games "${1:-6}" --visits "${2:-600}" --fsf-skill "${3:-2}" --movetime 400 --max-plies 500
