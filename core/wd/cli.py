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
    ("check", "Check the vault and the notes agents write.",
     "S0.2 (--measure) and S1.4"),
    ("score", "Score the linker against the links already in the vault.",
     "S0.4"),
    ("link", "Link every exact mention of an object.", "S1.3"),
    ("track", "Start tracking a word or phrase as a term.", "S1.7"),
    ("fix", "Apply a correction and record it as yours.", "S2.3"),
    ("find", "Find an object by name.", "S3.5"),
    ("pack", "Gather the context on one object.", "S3.5"),
    ("brief", "Write the daily brief.", "S3.2"),
    ("status", "Show what is declared and when each part last ran.", "S5.4"),
    ("tick", "The one scheduled entry point.", None),
    ("install", "Install a release file.", "S6.2"),
]

# Commands that are built. Each maps a name to a function that takes
# the remaining arguments and returns a code.
BUILT = {}


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
        return BUILT[name](arguments[1:])

    where = packages[name]
    if where:
        print("wd %s: not built yet. It arrives with package %s." % (name, where),
              file=err)
    else:
        print("wd %s: not built yet." % name, file=err)
    return NOT_BUILT
