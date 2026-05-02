"""
shared/setup.py

Makes the shared/ folder an installable Python package called
"collab_shared" so all services can import from it cleanly:

    from collab_shared.event_bus import publish_event
    from collab_shared.service_events import get_chat_service_subscriber

Installation in each service:
------------------------------
In services/<service-name>/requirements.txt, add:

    -e ../../shared

In services/<service-name>/Dockerfile, add BEFORE "COPY . /app":

    COPY ../../shared /shared
    RUN pip install --no-cache-dir -e /shared

Then in any file across any service:

    from collab_shared.event_bus import publish_event, EventBusSubscriber
    from collab_shared.service_events import get_chat_service_subscriber
"""

from setuptools import setup, find_packages

setup(
    name="collab_shared",
    version="0.1.0",
    description="Shared utilities for the collab-workspace microservices",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "redis>=5.0",
        "django>=4.2",
    ],
)