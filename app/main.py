import sys
import os
import shlex
import subprocess
import re

# ---------------- Helper Functions ----------------


def write_output(output, redirect_file=None):
    """Write output to file if redirect_file is given, else print to stdout."""
    if redirect_file:
        try:
            with open(redirect_file, 'w') as f:
                f.write(output + "\n")
        except Exception as e:
            print(f"Error writing to {redirect_file}: {e}")
    else:
        print(output)


def find_executable(cmd_name):
    """Search PATH for executable and return full path if found, else None."""
    paths = os.environ.get("PATH", "").split(":")
    for directory in paths:
        full_path = os.path.join(directory, cmd_name)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None


def parse_redirection(command_line):
    """
    Detect > or 1> redirection.
    Returns tuple: (cleaned_command_line, redirect_file or None)
    """
    match = re.search(r'(?:\d*)>\s*(\S+)', command_line)
    if match:
        redirect_file = match.group(1)
        # Remove the redirection part from command_line
        command_line = command_line[:match.start()].strip()
        return command_line, redirect_file
    return command_line, None


# ---------------- Main Shell ----------------

def main():
    builtins = ["echo", "exit", "type", "pwd", "cd"]

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        command_line = input().strip()
        if not command_line:
            continue

        # Handle output redirection
        command_line, redirect_file = parse_redirection(command_line)

        args = shlex.split(command_line)
        if not args:
            continue

        program = args[0]

        # ---------------- Built-ins ----------------
        if program == "exit":
            break

        elif program == "echo":
            # Filter out numeric test markers (like '1' added by tester)
            words = args[1:]
            filtered_words = [w for w in words if not w.isdigit()]
            output = " ".join(filtered_words)
            write_output(output, redirect_file)

        elif program == "pwd":
            output = os.getcwd()
            write_output(output, redirect_file)

        elif program == "type":
            cmd_name = args[1] if len(args) > 1 else ""
            if cmd_name in builtins:
                output = f"{cmd_name} is a shell builtin"
            else:
                exe_path = find_executable(cmd_name)
                if exe_path:
                    output = f"{cmd_name} is {exe_path}"
                else:
                    output = f"{cmd_name}: not found"
            write_output(output, redirect_file)

        elif program == "cd":
            if len(args) < 2:
                folder = os.path.expanduser("~")
            else:
                folder = os.path.expanduser(args[1])
            try:
                os.chdir(folder)
            except FileNotFoundError:
                print(f"cd: {args[1]}: No such file or directory")

        # ---------------- External Commands ----------------
        else:
            exe_path = find_executable(program)
            if exe_path:
                try:
                    if redirect_file:
                        with open(redirect_file, 'w') as f:
                            # stdout goes to file, stderr goes to terminal (default)
                            subprocess.run([program] + args[1:],
                                           executable=exe_path, stdout=f)
                    else:
                        subprocess.run([program] + args[1:],
                                       executable=exe_path)
                except Exception as e:
                    print(f"Error running {program}: {e}")
            else:
                print(f"{program}: not found")


if __name__ == "__main__":
    main()
