import sys
import os
import shlex
import subprocess


def main():
    builtins = ["echo", "exit", "type", "pwd", "cd"]

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        command_line = input().strip()
        if not command_line:
            continue

        # Detect output redirection
        redirect_file = None
        if '>' in command_line:
            parts = command_line.split('>', 1)
            command_line = parts[0].strip()
            redirect_file = parts[1].strip()

        args = shlex.split(command_line)
        if not args:
            continue
        program = args[0]

        # Handle builtins
        if program == "exit":
            break

        elif program == "echo":
            # Print everything except the last argument
            if len(args) > 2:
                output = " ".join(args[1:-1])
            elif len(args) == 2:
                output = args[1]
            else:
                output = ""

            if redirect_file:
                try:
                    with open(redirect_file, 'w') as f:
                        f.write(output + "\n")
                except Exception as e:
                    print(f"Error writing to {redirect_file}: {e}")
            else:
                print(output)

        elif program == "type":
            cmd_name = args[1] if len(args) > 1 else ""
            output = ""
            if cmd_name in builtins:
                output = f"{cmd_name} is a shell builtin"
            else:
                # Search PATH
                paths = os.environ.get("PATH", "").split(":")
                found = False
                for directory in paths:
                    full_path = os.path.join(directory, cmd_name)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        output = f"{cmd_name} is {full_path}"
                        found = True
                        break
                if not found:
                    output = f"{cmd_name}: not found"
            if redirect_file:
                try:
                    with open(redirect_file, 'w') as f:
                        f.write(output + "\n")
                except Exception as e:
                    print(f"Error writing to {redirect_file}: {e}")
            else:
                print(output)

        elif program == "pwd":
            output = os.getcwd()
            if redirect_file:
                try:
                    with open(redirect_file, 'w') as f:
                        f.write(output + "\n")
                except Exception as e:
                    print(f"Error writing to {redirect_file}: {e}")
            else:
                print(output)

        elif program == "cd":
            # If no argument, go home
            if len(args) < 2:
                folder = os.path.expanduser("~")
            else:
                folder = os.path.expanduser(args[1])
            try:
                os.chdir(folder)
            except FileNotFoundError:
                print(f"cd: {args[1]}: No such file or directory")

        else:
            # External commands
            paths = os.environ.get("PATH", "").split(":")
            found = False
            for directory in paths:
                full_path = os.path.join(directory, program)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    found = True
                    try:
                        if redirect_file:
                            with open(redirect_file, 'w') as f:
                                subprocess.run(
                                    [program] + args[1:], executable=full_path, stdout=f)
                        else:
                            subprocess.run([program] + args[1:],
                                           executable=full_path)
                    except Exception as e:
                        print(f"Error running {program}: {e}")
                    break
            if not found:
                print(f"{program}: not found")


if __name__ == "__main__":
    main()
