import logging
from providers.kcls import KCLSEventProvider
from providers.parentmap import ParentMapEventProvider

logging.basicConfig(
    filename='planner.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main(logger):
    logger.info("Fetching events from providers")

    kcls = KCLSEventProvider()
    kcls.download_events()

    parentmap = ParentMapEventProvider()
    parentmap.download_events()

    provider_events = {
        "KCLS": kcls.events,
        "ParentMap": parentmap.events
    }

    for provider, events in provider_events.items():
        print(f"Provider: {provider}")
        for event in events:
            print(f"Title: {event.title}")
            print(f"Status: {event.status}")
            print(f"Date: {event.date}")
            print(f"Time: {event.time}")
            print(f"Cost: {event.cost}")
            print(f"Location: {event.location}")
            print(f"Link: {event.link}")
            print(f"Description: {event.description}\n")


if __name__ == "__main__":
    main(logging.getLogger(__name__))
