import sys
import os
import shlex
import subprocess


def write_output(output, stdout_file=None, stderr_file=None):
    """Handle stdout + ensure stderr file is created if needed."""

    # Always create files if specified
    if stdout_file:
        open(stdout_file, 'w').close()
    if stderr_file:
        open(stderr_file, 'w').close()

    # Write stdout
    if stdout_file:
        with open(stdout_file, 'w') as f:
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
    """
    Handles:
    > file
    1> file
    2> file
    """
    stdout_file = None
    stderr_file = None

    tokens = command_line.split()
    clean_tokens = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token in [">", "1>"]:
            stdout_file = tokens[i + 1]
            i += 2
        elif token == "2>":
            stderr_file = tokens[i + 1]
            i += 2
        else:
            clean_tokens.append(token)
            i += 1

    return " ".join(clean_tokens), stdout_file, stderr_file


def main():
    builtins = ["echo", "exit", "type", "pwd", "cd"]

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            command_line = input().strip()
        except EOFError:
            break

        if not command_line:
            continue

        # Parse redirection
        command_line, stdout_file, stderr_file = parse_redirection(
            command_line)

        args = shlex.split(command_line)
        if not args:
            continue

        program = args[0]

        # ---------------- BUILTINS ----------------

        if program == "exit":
            break

        elif program == "echo":
            output = " ".join(args[1:])
            write_output(output, stdout_file, stderr_file)

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

            write_output(output, stdout_file, stderr_file)

        elif program == "cd":
            target = os.path.expanduser(args[1]) if len(
                args) > 1 else os.path.expanduser("~")

            try:
                os.chdir(target)

                # STILL create stderr file if requested
                if stderr_file:
                    open(stderr_file, 'w').close()

            except FileNotFoundError:
                error_msg = f"cd: {args[1]}: No such file or directory"

                if stderr_file:
                    with open(stderr_file, 'w') as f:
                        f.write(error_msg + "\n")
                else:
                    print(error_msg)

        # ---------------- EXTERNAL COMMANDS ----------------

        else:
            exe_path = find_executable(program)

            if not exe_path:
                print(f"{program}: not found")
                continue

            try:
                # Always create files first (IMPORTANT)
                if stdout_file:
                    open(stdout_file, 'w').close()
                if stderr_file:
                    open(stderr_file, 'w').close()

                stdout_f = open(stdout_file, 'w') if stdout_file else None
                stderr_f = open(stderr_file, 'w') if stderr_file else None

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
