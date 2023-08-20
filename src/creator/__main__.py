#!/usr/bin/python3
from .system_runner import Runner
from .logger import Logger
import argparse
import os
import subprocess
import re

runner = Runner()
logger = Logger()

path_pattern = r"^((~?/?|(\./)?)([a-zA-Z0-9_.\-]+/?)+)$"
device_pattern = r"^/dev/[a-zA-Z0-9]+$"
pool_types = 'stripe, mirror, raidz1, raidz2, raidz3'
default_encryption = 'aes-256-gcm'

def init_logger(log_path):
    global logger
    global runner
    logger = Logger(log_path)
    runner = Runner(logger)

def input_path(message, pattern):
    path = input(message).strip()
    while not validate_input(path, pattern):
        print("Invalid path. Please enter a valid path.")
        path = input(message).strip()
    return path

def input_name(message):
    name = input(message).strip()
    while not validate_input(name):
        print("Invalid name. Please enter a valid name.")
        name = input(message).strip()
    return name

def validate_input(value, pattern=None):
    if not value:
        return False

    if pattern and not re.match(pattern, value):
        return False

    return True

def validate_args(args, parser):
    if args.log_path:
        validate = validate_input(args.log_path, path_pattern)
        if not validate:
            display_error_with_args("Invalid log path", args, parser)
            exit(1)
        init_logger(args.log_path)

    if args.existed_key_path and args.key_path:
        display_error_with_args("Can't use simultaneosly \"-k, --key-path\" and \" -K, --existed-key-path \"", args, parser)
        exit(1)

    if args.key_path:
        validate = validate_input(args.key_path, path_pattern)
        if not validate:
            display_error_with_args("Invalid key path", args, parser)
            exit(1)
    
    if args.existed_key_path:
        validate = validate_input(args.existed_key_path, path_pattern)
        if not validate:
            display_error_with_args("Invalid existed key path", args, parser)
            exit(1)

    if args.pool_device:
        args.pool_device = [args.pool_device.strip() for device in args.pool_device.split(",")]
        for device in args.pool_device:
            validate = validate_input(device, device_pattern)
            if not validate:
                display_error_with_args("Invalid device path", args, parser)
                exit(1)

    if args.pool_name:
        validate = validate_input(args.pool_name)
        if not validate:
            display_error_with_args("Invalid pool name", args, parser)
            exit(1)

    if args.pool_type:
        validate = validate_input(args.pool_type)
        type_validate = args.pool_type in pool_types.split(', ')
        if not validate or not type_validate:
            display_error_with_args("Invalid pool type", args, parser)
            exit(1)

def validate_requirement_args(args):
    key_validation = bool(args.key_path) or bool(args.existed_key_path)
    other_validation = all([args.pool_device, args.pool_name])
    return key_validation and other_validation

def interactive_mode(args):
    if not args.key_path and not args.existed_key_path and not args.force:
        args.key_path = input_path("Input zfs key path, e.g. /remote/keystore/secret.key: ", path_pattern)
    
    if not args.pool_device:
        args.pool_device = select_drive_for_zfs_pool(args)
    
    if not args.pool_name:
        args.pool_name = input_name('Input zfs pool name, e.g. "tank" or "main1": ')

def display_error_with_args(error_message, args, parser):
    """
    Display an error message with all provided arguments.

    :param error_message: The main error message to display.
    :param args: The argparse.Namespace object containing all arguments.
    """
    print(f"ERROR: {error_message}\n")
    print("Provided arguments:")
    for arg, value in vars(args).items():
        print(f"  - {arg}: {value}")
    if parser: 
        print('')
        parser.print_help()

def error_file_not_exist(file):
    logger.error(f"File {file} does not exist.")
    exit(1)

def one_choose(choices):
    for i, choice in enumerate(choices, 1):
        print(f"{i}. {choice}")

    while True:
        try:
            selection = int(input("Enter your choice (number): "))
            if 1 <= selection <= len(choices):
                return choices[selection-1]
            else:
                print("Invalid choice. Please select again.")
        except ValueError:
            print("Please enter a number.")

def multi_choose(choices, message):
    for i, choice in enumerate(choices, 1):
        print(f"{i}. {choice}")
        
    while True:
        try:
            selections = input(message)
            selected_indices = [int(s.strip()) for s in selections.split(",")]

            if all(1 <= idx <= len(choices) for idx in selected_indices):
                return selected_indices
            else:
                print("Invalid choice. Please select again.")
        except ValueError:
            print("Please enter valid numbers separated by commas.")

def check_and_select_zfs_key(args):
    if args.key_path:
        if os.path.exists(args.key_path):
            logger.log(f'Selected ZFS keyfile {args.key_path}')
            return
        else:
            error_file_not_exist(args.key_path)
    else:
        files = [f for f in os.listdir(args.local_path) if os.path.isfile(os.path.join(args.local_path, f))]
        if not files:
            logger.error(f"No files found in {args.local_path}.")
            exit(1)
        selected = one_choose(files)
        args.key_path = os.path.join(args.local_path, files[selected])


def select_drive_for_zfs_pool(args):
    try:
        output = subprocess.check_output(['lsblk', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT'], universal_newlines=True)
    except subprocess.CalledProcessError:
        logger.error("Error getting block devices.")
        exit(1)

    devices = []
    for line in output.strip().split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "disk":
            devices.append(parts[0].strip())

    if not devices:
        logger.error("Error: no block devices found.")
        exit(1)
    
    selected_devices = []
    selected = multi_choose(devices, "Enter the numbers of the devices you want to select, separated by commas: ")
    for idx in selected:
        selected_device = f'/dev/{devices[idx - 1]}'
        logger.log(f'Select device {selected_device}')
        if not os.path.exists(selected_device):
            error_file_not_exist(selected_device)
        else:
            selected_devices.append(selected_device)
    return selected_devices


def is_package_installed(package):
    try:
        package_installed = runner.run(f"which {package}", silent=True)
        if package_installed == 0: 
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error during check {package} installed.")
        exit(1)

def create_zfs_keyfile(args):
    cmd = f'dd if=/dev/urandom of={args.key_path} bs=1 count=32'
    try:
        create_keyfile = runner.run(cmd)
        if create_keyfile == 0:
            return True
        return False
    except Exception as e:
        logger.error(f"Error during creation {args.key_path} key file.")
        exit(1)

def show_new_pool_information(args):
    cmd_status = ['zpool', 'status', f'{args.pool_name}']
    cmd_encryption = ['zfs', 'get', 'encryption,keyformat,keylocation', f'{args.pool_name}']
    try:
        output = subprocess.check_output(cmd_status, universal_newlines=True)
        logger.log('\n'+ output)
        output = subprocess.check_output(cmd_encryption, universal_newlines=True)
        logger.log('\n'+ output)
    except Exception as e:
        logger.error(f"Error during show status of new created pool {args.pool_name}. \n{e}")
        exit(1)

def create_zfs_pool(args):
    def error_creation():
        logger.error(f"Error during creation zfs pool {args.pool_name} type {args.pool_type} with key {args.key_path} for devices: {devices}.")
        exit(1)
        
    devices = ' '.join(args.pool_device)
    logger.log(f'Creating pool {args.pool_name} type {args.pool_type} with key {args.key_path} for devices: {devices}')
    cmd = f'zpool create -f -O keyformat=raw -O encryption={default_encryption} '
    if args.pool_type == 'stripe':
        cmd = cmd + f'-O keylocation=file://{args.key_path} {args.pool_name} {devices}'
    else:
        cmd = cmd + f'-O keylocation=file://{args.key_path} {args.pool_name} {args.pool_type} {devices}'
    logger.log(f'WARNING: Now you DESTOROY ALL data at {devices}')
    confirm = input('Are you sure? Please input "CONFIRM", if you sure: ').strip()
    if confirm == 'CONFIRM':
        logger.log(f'You confirm creating zfs pool {args.pool_name} type {args.pool_type} with key {args.key_path} for devices: {devices}.')
        try:
            result = runner.run(cmd)
            if result != 0:
                error_creation()
        except Exception as e:
            error_creation()
    else:
        logger.log('You are not confirm creating zfs pool')
        exit(0)

def is_file_size_32_bytes(file_path):
    return os.stat(file_path).st_size == 32

def main():
    required_packages = [ 'zfs', 'zpool', 'lsblk', ]

    for package in required_packages:
        if not is_package_installed(package):
            if package == 'zfs' or package == 'zpool':
                logger.error(f'Error: {package} is not installed. Please install it first. Example: apt install zfsutils-linux')
            else:
                logger.error(f'Error: {package} is not installed. Please install it first. Example: apt install {package}')
            exit(1)
   
    parser = argparse.ArgumentParser(description="ZFS encrypted pool create utility")
    parser.add_argument("-k", "--key-path", help="Path for ZFS key. If it does not exist, ask for create new file, e.g. /remote/keystore/secret.key")
    parser.add_argument("-f", "--force", action="store_true", help="Force creation key file, if it does not exist, without ask question.")
    parser.add_argument("-K", "--existed-key-path", help="Path for ZFS key. Exit with error, if it does not exist, e.g. /remote/keystore/secret.key")
    parser.add_argument("-d", "--pool-device", help='Selected devices for create ZFS pool, e.g. "/dev/sda1" or array comma separated "/dev/sda1, /dev/sda2" ')
    parser.add_argument("-n", "--pool-name", help='Name for ZFS pool, e.g. "tank" or "main1" ')
    parser.add_argument("-t", "--pool-type", 
                        help=f'Type for ZFS pool. Variants: {pool_types}. Default: stripe',
                        nargs="?",
                        const='stripe',
                        default='stripe'
                        )
    parser.add_argument("-q", "--quiet-mode", action="store_true", help="Quiet mode, disable interactive mode")
    parser.add_argument("-l", "--log-path", 
                    help='Log path, e.g. /var/log/ssh_mount_helper.log, default value "./ssh_mount_helper.log"',
                    nargs="?",
                    const="./ssh_mount_helper.log"
                    )
    args = parser.parse_args()
    validate_args(args, parser)
    try:
        if not args.quiet_mode: interactive_mode(args)
        validate_requirement_args(args)

        if args.key_path:
            if not os.path.exists(args.key_path):
                if args.force:
                    create_zfs_keyfile(args)
                else:
                    create_zfs_key = input("Would you like to create ZFS keyfile? (yes/no, default yes): ").strip().lower()
                    if not create_zfs_key or create_zfs_key == 'yes':
                        create_zfs_keyfile(args)
        

        if args.existed_key_path:
            if not os.path.exists(args.existed_key_path):
                error_file_not_exist(args.existed_key_path)
            else:
                args.key_path = args.existed_key_path

        for device in args.pool_device:
            if not os.path.exists(device):
                logger.error(f'Device {device} does not exist')
                exit(1)

        if os.path.exists(args.key_path):
            if not is_file_size_32_bytes(args.key_path):
                logger.error(f'For encryption {default_encryption} you must use key file with size 32 bytes.'+
                             '\n\t You can create new by script, or manually by command: ' + 
                             f'\n\t rm -rf {args.key_path} && dd if=/dev/urandom of={args.key_path} bs=1 count=32')
                exit(1)
            create_zfs_pool(args)
            show_new_pool_information(args)

    except KeyboardInterrupt:
        logger.log('Script interrupted by user')

if __name__ == "__main__":
    main()