"""The `wd` command.

Every command prints plain results and returns a failure code when
something is wrong. A command that is not built yet says so and fails.
"""

import sys

OK = 0
FAILED = 1
USAGE = 2
NOT_BUILT = 3

# The commands fixed by the build spec, in its order. Each carries one
# line on what it does and the work package that builds it.
COMMANDS = [
    ("init", "Make a new, empty vault.", "S1.3"),
    ("check", "Check the vault and the notes agents write.",
     "S0.2 (--measure) and S1.4"),
    ("score", "Score the linker against the links already in the vault.",
     "S0.4"),
    ("status", "Write the status page: what is there and what a session loads.",
     "S1.4"),
    ("graph-setting", "Write the graph's colors and what it hides.", "S1.3"),
    ("add", "Bring a source in and give it its permanent home.", "S2.1"),
    ("process", "Turn a source into objects, links and history lines.", "S2.4"),
    ("link", "Link every exact mention of an object.", "S2.2"),
    ("track", "Start tracking a word or phrase as a term.", "S2.5"),
    ("fix", "Apply a correction and record it as yours.", "S2.5"),
    ("find", "Find an object by name.", "S4.5"),
    ("pack", "Gather the context on one object.", "S4.5"),
    ("brief", "Write the daily brief.", "S4.2"),
    ("tick", "The one scheduled entry point.", "S4.6"),
    ("install", "Install a release file.", "S7.2"),
]


def check(arguments, out, err):
    """`wd check --measure <vault>` is built. Plain `wd check` is not yet."""
    if arguments and arguments[0] == "--measure":
        from wd import measure
        return measure.run(arguments[1:], out, err)
    print("wd check: not built yet. It arrives with package S1.4. "
          "`wd check --measure <vault>` is built.", file=err)
    return NOT_BUILT


def score(arguments, out, err):
    """`wd score <vault>`, the stage 0 scorer."""
    import score as scorer
    return scorer.run(arguments, out, err)


# Commands that are built. Each maps a name to a function that takes
# the remaining arguments, where to print, and returns a code.
BUILT = {"check": check, "score": score}


def usage():
    lines = ["usage: wd <command> [arguments]", "", "commands:"]
    width = max(len(name) for name, _, _ in COMMANDS)
    for name, what, _ in COMMANDS:
        lines.append("  %s  %s" % (name.ljust(width), what))
    return "\n".join(lines)


def main(arguments=None, out=None, err=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    out = out or sys.stdout
    err = err or sys.stderr

    if not arguments:
        print(usage(), file=err)
        return USAGE
    name = arguments[0]
    if name in ("-h", "--help", "help"):
        print(usage(), file=out)
        return OK

    packages = {command: package for command, _, package in COMMANDS}
    if name not in packages:
        print("wd: there is no command called '%s'." % name, file=err)
        print(usage(), file=err)
        return USAGE
    if name in BUILT:
        from wd import declarations
        try:
            return BUILT[name](arguments[1:], out, err)
        except declarations.DeclarationError as problem:
            print("wd %s: %s" % (name, problem), file=err)
            return FAILED

    where = packages[name]
    if where:
        print("wd %s: not built yet. It arrives with package %s." % (name, where),
              file=err)
    else:
        print("wd %s: not built yet." % name, file=err)
    return NOT_BUILT
