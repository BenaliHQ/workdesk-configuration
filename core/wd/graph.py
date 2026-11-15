"""What shows in the graph, and which objects have no link in or out.

Contract rule 5: the graph holds the objects, the syntheses and the
owner's writing. Sources are hidden link targets. Briefs and the files
at the top of a vault are outside it.

This is the one rule for "unlinked". `wd check`, `wd check --measure`
and the status page all use it.
"""

from wd import notes, places


def objects(vault):
    """Every object note, home by home in the build spec's order."""
    return [
        name for _, folder in places.OBJECT_HOMES
        for name in vault.notes if places.in_home(name, folder)
    ]


def shown(vault):
    """The notes that show in the graph: objects, syntheses and the owner's writing."""
    folders = [folder for _, folder in places.OBJECT_HOMES]
    folders += [places.SYNTHESES, places.WRITING]
    return {
        name for name in vault.notes
        if any(places.in_home(name, folder) for folder in folders)
    }


def unlinked_objects(vault):
    """Objects with no link to or from another note that shows in the graph.

    A link counts wherever it is written in a note, so a meeting's
    `attendees` list counts. A link to or from a source does not count,
    and neither does a source's `produced` list, a brief, or a file at
    the top of the vault: none of those show in the graph. The owner's
    writing is read for its links and never written.
    """
    in_graph = shown(vault)
    connected = set()
    for name in sorted(in_graph):
        for target in notes.link_targets(vault.text(name)):
            found = vault.resolve(target, name)
            if found and found != name and found in in_graph:
                connected.add(name)
                connected.add(found)
    return [name for name in objects(vault) if name not in connected]
