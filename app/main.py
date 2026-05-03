import sys
import os
import shlex
import subprocess
import readline
import glob

EXECUTABLES = set()
TAB_COUNT = 0
LAST_BUFFER = ""


def write_output(output, stdout_file=None, stderr_file=None, append_stdout=False):
    mode = 'a' if append_stdout else 'w'

    # Create files
    if stdout_file:
        open(stdout_file, mode).close()
    if stderr_file:
        open(stderr_file, 'w').close()

    # Write stdout
    if stdout_file:
        with open(stdout_file, mode) as f:
            f.write(output + "\n")
    else:
        print(output)


def find_executable(cmd_name):
    """Find executable in PATH."""
    for directory in os.environ.get("PATH", "").split(":"):
        full_path = os.path.join(directory, cmd_name)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None


def parse_redirection(command_line):
    tokens = shlex.split(command_line)

    stdout_file = None
    stderr_file = None
    append_stdout = False
    append_stderr = False

    clean_tokens = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # --- STDOUT ---
        if token in [">", "1>"]:
            stdout_file = tokens[i + 1]
            append_stdout = False
            i += 2

        elif token in [">>", "1>>"]:
            stdout_file = tokens[i + 1]
            append_stdout = True
            i += 2

        # --- STDERR ---
        elif token == "2>":
            stderr_file = tokens[i + 1]
            append_stderr = False
            i += 2

        elif token == "2>>":
            stderr_file = tokens[i + 1]
            append_stderr = True
            i += 2

        else:
            clean_tokens.append(token)
            i += 1

    return clean_tokens, stdout_file, stderr_file, append_stdout, append_stderr


def completer(text, state):
    buffer = readline.get_line_buffer()
    tokens = buffer.split()

    if len(tokens) <= 1:
        prefix = text

        builtins = ["echo", "exit"]
        executables = EXECUTABLES or []

        matches = sorted(
            cmd for cmd in (builtins + list(executables))
            if cmd.startswith(prefix)
        )

        if state < len(matches):
            return matches[state] + " "

        return None

    prefix = tokens[-1] if buffer[-1] != " " else ""

    matches = sorted(glob.glob(prefix + "*"))

    if state < len(matches):
        match = matches[state]

        if os.path.isdir(match):
            return match + "/"

        return match + " "

    return None


def get_executables():
    executables = set()

    for directory in os.environ.get("PATH", "").split(":"):
        if not os.path.isdir(directory):
            continue

        try:
            for file in os.listdir(directory):
                full_path = os.path.join(directory, file)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    executables.add(file)
        except PermissionError:
            continue

    return executables


def setup_autocomplete():
    global EXECUTABLES

    EXECUTABLES = get_executables()

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")

    readline.set_completer_delims(" \t\n")


def main():
    builtins = ["echo", "exit", "type", "pwd", "cd"]

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")

    setup_autocomplete()

    while True:
        try:
            command_line = input("$ ")
        except EOFError:
            break

        if not command_line:
            continue

        args, stdout_file, stderr_file, append_stdout, append_stderr = parse_redirection(
            command_line
        )

        if not args:
            continue

        program = args[0]

        # ---------------- BUILTINS ----------------

        if program == "exit":
            break

        elif program == "echo":
            output = " ".join(args[1:])
            write_output(output, stdout_file, stderr_file, append_stdout)

        elif program == "pwd":
            write_output(os.getcwd(), stdout_file, stderr_file)

        elif program == "type":
            cmd = args[1] if len(args) > 1 else ""

            if cmd in builtins:
                output = f"{cmd} is a shell builtin"
            else:
                path = find_executable(cmd)
                if path:
                    output = f"{cmd} is {path}"
                else:
                    output = f"{cmd}: not found"

            write_output(output, stdout_file, stderr_file, append_stdout)

        elif program == "cd":
            target = os.path.expanduser(args[1]) if len(
                args) > 1 else os.path.expanduser("~")

            try:
                os.chdir(target)
            except FileNotFoundError:
                error_msg = f"cd: {args[1]}: No such file or directory"

                # FIX: stderr must always go to write_output OR print cleanly
                if stderr_file:
                    write_output(error_msg, stderr_file)
                else:
                    print(error_msg)

        # ---------------- EXTERNAL COMMANDS ----------------

        else:
            exe_path = find_executable(program)

            if not exe_path:
                print(f"{program}: not found")
                continue

            try:
                stdout_mode = 'a' if append_stdout else 'w'
                stderr_mode = 'a' if append_stderr else 'w'

                stdout_f = open(
                    stdout_file, stdout_mode) if stdout_file else None
                stderr_f = open(
                    stderr_file, stderr_mode) if stderr_file else None

                subprocess.run(
                    [program] + args[1:],
                    executable=exe_path,
                    stdout=stdout_f,
                    stderr=stderr_f
                )

                if stdout_f:
                    stdout_f.close()
                if stderr_f:
                    stderr_f.close()

            except Exception as e:
                print(f"Error running {program}: {e}")


if __name__ == "__main__":
    main()
