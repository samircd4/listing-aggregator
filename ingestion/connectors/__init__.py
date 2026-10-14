from .catchbuys import CatchBuysConnector

REGISTRY = {cls.slug: cls for cls in (CatchBuysConnector,)}


def get_connector(source):
    return REGISTRY[source.slug](source)
