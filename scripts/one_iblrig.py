#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Saturday, May 18th 2019, 12:59:43 pm
import ibllib.pipes.iblrig.one_iblrig as o
import argparse


if __name__ == "__main__":
    ALLOWED_ACTIONS = ['create', 'extract', 'register', 'compress_video']
    parser = argparse.ArgumentParser(description='Description of your program')
    parser.add_argument('action', help='Action: ' + ','.join(ALLOWED_ACTIONS))
    parser.add_argument('folder', help='A Folder containing a session')
    parser.add_argument('--dry', help='Dry Run', required=False, default=False, type=str)
    parser.add_argument('--count', help='Max number of sessions to run this on',
                        required=False, default=False, type=int)
    args = parser.parse_args()  # returns data from the options specified (echo)
    if args.dry and args.dry.lower() == 'false':
        args.dry = False
    assert(Path(args.folder).exists())
    if args.action == 'extract':
        extract(args.folder, dry=args.dry)
    elif args.action == 'register':
        register(args.folder, dry=args.dry)
    elif args.action == 'create':
        create(args.folder, dry=args.dry)
    elif args.action == 'compress_video':
        compress_video(args.folder, dry=args.dry, max_sessions=args.count)
    else:
        logger.error('Allowed actions are: ' + ', '.join(ALLOWED_ACTIONS))
