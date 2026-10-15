"""Automated fixtures must never inherit a developer's live .env mode."""

import os

os.environ['BIKESHARE_APP_MODE'] = 'fixture_demo'
