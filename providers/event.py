class Event:
    def __init__(self, title, link, date, cost, location, description, status="Confirmed", time=None, provider=None, type="Onsite"):
        self.title = title
        self.link = link
        self.date = date
        self.cost = cost
        self.location = location
        self.description = description
        self.status = status
        self.time = time
        self.provider = provider
        self.type = type

    def __repr__(self):
        return f"{self.provider} event: {self.title} on {self.date} at {self.location}"

class EventProvider:
    def __init__(self):
        self.events = []

    def get_event(self):
        pass
