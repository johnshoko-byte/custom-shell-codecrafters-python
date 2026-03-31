import sys
import os


def main():
    builtins = ["echo", "exit", "type"]

    while True:
        # Display prompt
        sys.stdout.write("$ ")
        sys.stdout.flush()  # Make sure $ shows immediately

        command = input().strip()
        if not command:
            continue  # Skip empty commands

        # Exit command
        if command == "exit":
            break

        # Echo command
        elif command.startswith("echo "):
            print(command[5:])

        # Type command
        elif command.startswith("type "):
            cmd_name = command[5:]

            # Check if builtin
            if cmd_name in builtins:
                print(f"{cmd_name} is a shell builtin")
                continue

            # Search PATH for executable
            paths = os.environ.get("PATH", "").split(":")
            found = False
            for directory in paths:
                full_path = os.path.join(directory, cmd_name)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    print(f"{cmd_name} is {full_path}")
                    found = True
                    break

            if not found:
                print(f"{cmd_name}: not found")

        # Unknown command
        else:
            print(f"{command}: command not found")


if __name__ == "__main__":
    main()
