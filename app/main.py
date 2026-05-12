import sys
import os
import shlex
import subprocess
import readline

EXECUTABLES = set()
TAB_COUNT = 0
LAST_BUFFER = ""
MULTI_MATCH_READY = False
JOBS = []
JOB_NUMBER = 1


def write_output(output, stdout_file=None, stderr_file=None, append_stdout=False):
    mode = 'a' if append_stdout else 'w'

    if stdout_file:
        open(stdout_file, mode).close()
    if stderr_file:
        open(stderr_file, 'w').close()

    if stdout_file:
        with open(stdout_file, mode) as f:
            f.write(output + "\n")
    else:
        print(output)


def find_executable(cmd_name):
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

        if token in [">", "1>"]:
            stdout_file = tokens[i + 1]
            append_stdout = False
            i += 2

        elif token in [">>", "1>>"]:
            stdout_file = tokens[i + 1]
            append_stdout = True
            i += 2

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
    parts = buffer.split()

    # ---------------- COMMAND COMPLETION ----------------
    if len(parts) <= 1 and not buffer.endswith(" "):
        builtins = ["echo", "exit"]
        executables = EXECUTABLES or []

        matches = sorted(
            cmd for cmd in (builtins + list(executables))
            if cmd.startswith(text)
        )

        if not matches:
            sys.stdout.write("\x07")
            sys.stdout.flush()
            return None

        if state < len(matches):
            return matches[state] + " "
        return None

    # ---------------- FILE / DIRECTORY COMPLETION ----------------
    token = text

    # CASE 1: token ends with /
    # example: pig/
    if token.endswith("/"):
        search_dir = token[:-1]
        prefix = ""
    else:
        search_dir = os.path.dirname(token)
        prefix = os.path.basename(token)

    if search_dir == "":
        search_dir = "."

    try:
        entries = sorted(os.listdir(search_dir))
    except FileNotFoundError:
        sys.stdout.write("\x07")
        sys.stdout.flush()
        return None

    matches = [e for e in entries if e.startswith(prefix)]

    if not matches:
        sys.stdout.write("\x07")
        sys.stdout.flush()
        return None

    if state >= len(matches):
        return None

    match = matches[state]

    # rebuild proper completed path
    if search_dir == ".":
        completed = match
    else:
        completed = os.path.join(search_dir, match)

    full_match_path = os.path.join(search_dir, match)

    # directory
    if os.path.isdir(full_match_path):
        return completed + "/"

    # file
    return completed + " "


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
    builtins = ["echo", "exit", "type", "pwd", "cd", "jobs"]

    setup_autocomplete()

    while True:
        try:
            command_line = input("$ ")

            original_command = command_line

        except EOFError:
            break

        if not command_line:
            continue

        args, stdout_file, stderr_file, append_stdout, append_stderr = parse_redirection(
            command_line
        )

        if not args:
            continue

        background = False

        if args[-1] == "&":
            background = True
            args = args[:-1]

            if not args:
                continue

        program = args[0]

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

                if stderr_file:
                    write_output(error_msg, stderr_file)
                else:
                    print(error_msg)

        elif program == "jobs":
            for job in JOBS:
                print(f"[{job['id']}]+  {'Running':<24}{job['command']}")

        else:
            global JOB_NUMBER

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

                # BACKGROUND PROCESS
                if background:
                    process = subprocess.Popen(
                        [program] + args[1:],
                        executable=exe_path,
                        stdout=stdout_f,
                        stderr=stderr_f
                    )

                    print(f"[{JOB_NUMBER}] {process.pid}")

                    JOBS.append({
                        "id": JOB_NUMBER,
                        "pid": process.pid,
                        "command": original_command,
                        "status": "Running"
                    })

                    JOB_NUMBER += 1

                # FOREGROUND PROCESS
                else:
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
