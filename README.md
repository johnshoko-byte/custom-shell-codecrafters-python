# pysh — A Custom Python Shell

A Unix-like shell written in Python, supporting job control, pipelines, I/O redirection, tab completion, programmable completers, and shell variables.

---

## Features

### Built-in commands

| Command | Description |
|---|---|
| `echo` | Print arguments to stdout |
| `pwd` | Print current working directory |
| `cd [dir]` | Change directory (defaults to `~`) |
| `type <cmd>` | Show whether a command is a builtin or external executable |
| `jobs` | List background jobs and their status |
| `history` | Show command history |
| `declare` | Declare and inspect shell variables |
| `complete` | Register or remove programmable tab completers |
| `exit` | Exit the shell |

---

### I/O Redirection

| Syntax | Effect |
|---|---|
| `cmd > file` | Redirect stdout to file (overwrite) |
| `cmd >> file` | Redirect stdout to file (append) |
| `cmd 2> file` | Redirect stderr to file |
| `cmd 2>> file` | Redirect stderr to file (append) |

---

### Pipelines

Chain commands with `|`:

```bash
$ echo hello | cat
hello
```

Builtins and external commands can be mixed in pipelines.

---

### Background jobs

Append `&` to run a command in the background:

```bash
$ sleep 5 &
[1] 12345
```

Use `jobs` to list running and completed background processes.

---

### Tab completion

- **Single match** — completes immediately with a trailing space.
- **Partial prefix** — expands to the longest common prefix across all matches.
- **Multiple matches** — rings the bell on the first Tab, then lists all matches on the second Tab.
- **File/directory completion** — completes paths; directories get a trailing `/`.

---

### Programmable completion

Register a completion script for any command using `complete -C`:

```bash
$ complete -C /path/to/script git
```

The script is called with `argv[1]=command`, `argv[2]=current_word`, `argv[3]=previous_word`, and the environment variables `COMP_LINE` and `COMP_POINT` set to the full command line and cursor position.

Remove a completion rule with:

```bash
$ complete -r git
```

Inspect a registered rule with:

```bash
$ complete -p git
```

---

### Shell variables

Declare variables with `declare`:

```bash
$ declare greeting=hello
$ declare -p greeting
declare -- greeting="hello"
```

Variable names must be valid identifiers: start with a letter or `_`, followed by letters, digits, or underscores.

**Parameter expansion** — use `$VAR` or `${VAR}` in any command:

```bash
$ declare name=world
$ echo hello $name
hello world
$ echo file_${name}_end
file_world_end
```

Unset variables expand to an empty string. Words that expand entirely to empty are dropped from the argument list.

---

### History

```bash
$ history          # show all history
$ history 10       # show last 10 entries
$ history -w file  # write history to file
$ history -r file  # read history from file
$ history -a file  # append new entries to file
```

History is loaded from and saved to the file specified by the `HISTFILE` environment variable on startup and exit.

---

## Running

```bash
$ python main.py
```

Or via a wrapper script:

```bash
$ ./your_program.sh
```

---

## Project structure

```
main.py        # Entry point and main REPL loop
```

All logic lives in `main.py`, including the completer, parser, builtin dispatcher, job manager, and variable store.
